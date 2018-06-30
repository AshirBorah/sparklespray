import logging
import os
import json
import sys

import kubeque
from .task_store import STATUS_FAILED, STATUS_CLAIMED, STATUS_PENDING, STATUS_KILLED, STATUS_COMPLETE
from .util import get_timestamp, url_join

import csv
import argparse

log = logging.getLogger(__name__)

def list_params_cmd(jq, io, args):
    jobid = _resolve_jobid(jq, args.jobid)
    retcode = args.exitcode
    include_extra = args.extra

    if args.incomplete:
        tasks = []
        for status in [STATUS_FAILED, STATUS_CLAIMED, STATUS_PENDING, STATUS_KILLED]:
            tasks.extend(jq.get_tasks(jobid, status=status))
    else:
        tasks = jq.get_tasks(jobid)

    if retcode is not None:
        def retcode_matches(exit_code):
            return exit_code is not None and int(exit_code) == retcode

        before_count = len(tasks)
        tasks = [task for task in tasks if retcode_matches(task.exit_code)]
        print("Filtered {} tasks to {} tasks with exit code {}".format(before_count, len(tasks), retcode))

    if len(tasks) == 0:
        print("No tasks found")
    else:
        print("Getting parameters from %d tasks" % len(tasks))
        parameters = []
        for task in tasks:
            task_spec = json.loads(io.get_as_str(task.args))
            task_parameters = task_spec.get('parameters', {})
            if include_extra:
                task_parameters['task_id'] = task.task_id
                task_parameters['exit_code'] = task.exit_code
            parameters.append(task_parameters)

        # find the union of all keys
        keys = set()
        for p in parameters:
            keys.update(p.keys())

        columns = list(keys)
        columns.sort()

        with open(args.filename, "wt") as fd:
            w = csv.writer(fd)
            w.writerow(columns)
            for p in parameters:
                row = [str(p.get(column, "")) for column in columns]
                w.writerow(row)


def reset_cmd(jq, args):
    for jobid in _get_jobids_from_pattern(jq, args.jobid_pattern):
        if args.all:
            statuses_to_clear = [STATUS_CLAIMED, STATUS_FAILED, STATUS_COMPLETE, STATUS_KILLED]
        else:
            statuses_to_clear = [STATUS_CLAIMED, STATUS_FAILED, STATUS_KILLED]
        log.info("reseting %s by changing tasks with statuses (%s) -> %s", jobid, ",".join(statuses_to_clear),
                 STATUS_PENDING)
        updated = jq.reset(jobid, args.owner, statuses_to_clear=statuses_to_clear)
        log.info("updated %d tasks", updated)
        if args.resubmit:
            _resubmit(jq, jobid)


def _summarize_task_statuses(tasks):
    import collections
    complete = True
    counts = collections.defaultdict(lambda: 0)
    for task in tasks:
        if task.status == STATUS_COMPLETE:
            label = "{}(code={})".format(task.status, task.exit_code)
        elif task.status == STATUS_FAILED:
            label = "{}({})".format(task.status, task.failure_reason)
        else:
            label = task.status
        counts[label] += 1

        if not _is_terminal_status(task.status):
            complete = False

    labels = list(counts.keys())
    labels.sort()
    status_str = ", ".join(["{}: {}".format(l, counts[l]) for l in labels])
    return status_str, complete


def _get_jobids_from_pattern(jq, jobid_pattern):
    if not jobid_pattern:
        jobid_pattern = "*"

    if jobid_pattern == "LAST":
        job = jq.get_last_job()
        return [job.job_id]
    else:
        return jq.get_jobids(jobid_pattern)


def _resolve_jobid(jq, jobid):
    if jobid == "LAST":
        job = jq.get_last_job()
        return job.job_id
    else:
        return jobid


def saturate_cmd(jq, io, cluster, args):
    jobid = _resolve_jobid(jq, args.jobid)
    watch(io, jq, jobid, cluster, saturate=True, saturate_nodes=args.nodes)

def status_cmd(jq, io, cluster, args):
    jobids = _get_jobids_from_pattern(jq, args.jobid_pattern)

    if args.wait or args.loglive:
        assert len(jobids) == 1, "When watching, only one jobid allowed, but the following matched wildcard: {}".format(
            jobids)
        jobid = jobids[0]
        watch(io, jq, jobid, cluster, loglive=args.loglive)
    else:
        for jobid in jobids:
            if args.detailed or args.failures:
                for task in jq.get_tasks(jobid):
                    if args.failures and task.status != STATUS_FAILED:
                        continue

                    command_result_json = None
                    if task.command_result_url is not None:
                        command_result_json = io.get_as_str(task.command_result_url, must=False)
                    if command_result_json is not None:
                        command_result = json.loads(command_result_json)
                        command_result_block = "\n  command result: {}".format(json.dumps(command_result, indent=4))
                    else:
                        command_result_block = ""

                    log.info("task_id: %s\n"
                             "  status: %s, exit_code: %s, failure_reason: %s\n"
                             "  started on pod: %s\n"
                             "  args: %s, history: %s%s\n"
                             "  cluster: %s", task.task_id,
                             task.status, task.exit_code, task.failure_reason, task.owner, task.args, task.history,
                             command_result_block, task.cluster)
            else:
                tasks = jq.get_tasks(jobid)
                status, complete = _summarize_task_statuses(tasks)
                log.info("%s: %s", jobid, status)

def _commonprefix(paths):
    "Given a list of paths, returns the longest common prefix"
    if not paths:
        return ()

    # def split(path):
    #     return [x for x in path.split("/") if x != ""]

    paths = [x.split("/") for x in paths]

    min_path = min(paths)
    max_path = max(paths)
    common_path = min_path
    for i in range(len(min_path)):
        if min_path[i] != max_path[i]:
            common_path = common_path[:i]
            break

    return "/".join(common_path)

def fetch_cmd(jq, io, args):
    jobid = _resolve_jobid(jq, args.jobid)
    if args.dest is None:
        dest = jobid
    else:
        dest = args.dest
    fetch_cmd_(jq, io, jobid, dest, flat=args.flat)


def fetch_cmd_(jq, io, jobid, dest_root, force=False, flat=False):
    def get(src, dst, **kwargs):
        if os.path.exists(dst) and not force:
            log.warning("%s exists, skipping download", dst)
        return io.get(src, dst, **kwargs)

    tasks = jq.get_tasks(jobid)

    if not os.path.exists(dest_root):
        os.mkdir(dest_root)

    include_index = not flat

    for task in tasks:
        spec = json.loads(io.get_as_str(task.args))
        log.debug("task %d spec: %s", task.task_index + 1, spec)

        if include_index:
            dest = os.path.join(dest_root, str(task.task_index + 1))
            if not os.path.exists(dest):
                os.mkdir(dest)
        else:
            dest = dest_root

        # save parameters taken from spec
        # with open(os.path.join(dest, "parameters.json"), "wt") as fd:
        #     fd.write(json.dumps(spec['parameters']))
        command_result_json = io.get_as_str(spec['command_result_url'], must=False)
        to_download = []
        if command_result_json is None:
            log.warning("Results did not appear to be written yet at %s", spec['command_result_url'])
        else:
            get(spec['stdout_url'], os.path.join(dest, "stdout.txt"))
            command_result = json.loads(command_result_json)
            log.debug("command_result: %s", json.dumps(command_result))
            for ul in command_result['files']:
                to_download.append((ul['src'], ul['dst_url']))

        for src, dst_url in to_download:
            if include_index:
                localpath = os.path.join(dest_root, str(task.task_index + 1), src)
            else:
                localpath = os.path.join(dest_root, src)
            pdir = os.path.dirname(localpath)
            if not os.path.exists(pdir):
                os.makedirs(pdir)
            get(dst_url, localpath)


def _is_terminal_status(status):
    return status in [STATUS_FAILED, STATUS_COMPLETE]


def _is_complete(status_counts):
    all_terminal = True
    for status in status_counts.keys():
        if not _is_terminal_status(status):
            all_terminal = True
    return all_terminal


class NodeRespawn:
    def __init__(self, cluster_status_fn, tasks_status_fn, get_pending_fn, max_nodes):
        self.max_restarts = tasks_status_fn().active_tasks
        self.cluster_status_fn = cluster_status_fn
        self.tasks_status_fn = tasks_status_fn
        self.last_cluster_status = None
        self.nodes_added = 0
        self.max_nodes = max_nodes
        self.get_pending_fn = get_pending_fn

    def reset_added_count(self):
        self.nodes_added = 0

    def reconcile_node_count(self, add_node_callback):
        # get latest status
        cluster_status = self.tasks_status_fn()
        if cluster_status == self.last_cluster_status:
            # don't try to reconcile if we see the identical as last time we polled. We might not
            # be able to see newly spawned nodes yet, so wait for the next poll
            return

        needed_nodes = cluster_status.active_tasks
        if self.max_nodes is not None:
            needed_nodes = min(self.max_nodes, needed_nodes)
        running_count = self.cluster_status_fn().running_count
        # for now, count pending requests as "running" because they eventually will
        #print("calling get_pending_fn")
        running_count += self.get_pending_fn()
        self.last_cluster_status = cluster_status

        # see if we're short and add nodes of the appropriate type
        if needed_nodes > running_count:
            nodes_to_add = needed_nodes - running_count
            capped_nodes_to_add = min(nodes_to_add, self.max_restarts - self.nodes_added)
            if capped_nodes_to_add == 0:
                raise Exception("Wanted to add {} nodes, but we have reached our limit on how many nodes can be restarted ({})".format(nodes_to_add, self.max_restarts))
            else:
                add_node_callback(capped_nodes_to_add)
                self.nodes_added += capped_nodes_to_add
                log.info("Added {} nodes (total: {}/{})".format(capped_nodes_to_add, self.nodes_added, self.max_restarts))

class TasksStatus:
    def __init__(self, tasks):
        self.tasks = tasks

    @property
    def active_tasks(self):
        # compute how many nodes are needed to run everything in parallel
        last_needed_nodes = 0
        for task in self.tasks:
            if task.status in [STATUS_CLAIMED, STATUS_PENDING]:
                last_needed_nodes += 1
        return last_needed_nodes

    @property
    def failed_tasks(self):
        failures = 0
        for task in self.tasks:
            if task.status in [STATUS_FAILED]:
                failures += 1
            elif task.status in [STATUS_COMPLETE]:
                if str(task.exit_code) != "0":
                    failures += 1
        return failures

    @property
    def summary(self):
        return _summarize_task_statuses(self.tasks)


def addnodes_cmd(jq, cluster, args, config):
    job_id = _resolve_jobid(jq, args.job_id)
    return _addnodes(job_id, jq, cluster, args.count, None, config['default_url_prefix'])

def _addnodes(job_id, jq, cluster, count, preemptible, default_url_prefix):
    job = jq.get_job(job_id)
    log.info("Adding %d nodes to cluster %s", count, job.cluster)
    operation_ids = []
    timestamp = get_timestamp()
    for i in range(count):
        debug_log_url = url_join(default_url_prefix, "node-logs", job_id, timestamp, "output-{}.log".format(i))
        operation_id = jq.add_node(job_id, cluster, preemptible, debug_log_url, job=job)
        log.info("adding node via operation %s, logs will be written to %s", operation_id, debug_log_url)
        operation_ids.append(operation_id)
    return operation_ids

def _resub_preempted(cluster, jq, jobid):
    tasks = jq.get_tasks(jobid, STATUS_CLAIMED)
    for task in tasks:
        _update_if_owner_missing(cluster, jq, task)

def _clean(cluster, jq, jobid, force=False):
    if not force:
        status_counts = jq.get_status_counts(jobid)
        log.debug("job %s has status %s", jobid, status_counts)
        if STATUS_CLAIMED in status_counts:
            # if some tasks are still marked 'claimed' verify that the owner is still running
            tasks = jq.get_tasks(jobid, STATUS_CLAIMED)
            for task in tasks:
                _update_if_owner_missing(cluster, jq, task)

            # now that we may have changed some tasks from claimed -> pending, check again
            status_counts = jq.get_status_counts(jobid)
            if STATUS_CLAIMED in status_counts:
                log.warning("job %s is still running (%s), cannot remove", jobid, status_counts)
                return False

    log.info("deleting %s", jobid)
    jq.delete_job(jobid)
    return True

def clean_cmd(cluster, jq, args):
    log.info("jobid_pattern: %s", args.jobid_pattern)
    jobids = _get_jobids_from_pattern(jq, args.jobid_pattern)
    for jobid in jobids:
        _clean(cluster, jq, jobid, args.force)

def _update_if_owner_missing(cluster, jq, task):
    if task.status != STATUS_CLAIMED:
        return
    if not cluster.is_owner_running(task.owner):
        job = jq.get_job(task.job_id)
        if job.status == JOB_STATUS_KILLED:
            new_status = STATUS_KILLED
        else:
            new_status = STATUS_PENDING
        log.info("Task %s is owned by %s which does not appear to be running, resetting status from 'claimed' to '%s'", task.task_id, task.owner, new_status)
        jq.reset_task(task.task_id, status= new_status)

def kill_cmd(jq, cluster, args):
    jobids = _get_jobids_from_pattern(jq, args.jobid_pattern)
    if len(jobids) == 0:
        log.warning("No jobs found matching pattern")
    for jobid in jobids:
        # TODO: stop just marks the job as it shouldn't run any more.  tasks will still be claimed.
        log.info("Marking %s as killed", jobid)
        ok, job = jq.kill_job(jobid)
        assert ok
        if not args.keepcluster:
            cluster.stop_cluster(job.cluster)
            tasks = jq.get_tasks_for_cluster(job.cluster, STATUS_CLAIMED)
            for task in tasks:
                _update_if_owner_missing(cluster, jq, task)

        # if there are any sit sitting at pending, mark them as killed
        tasks = jq.get_tasks(jobid, status=STATUS_PENDING)
        for task in tasks:
            jq.reset_task(task.task_id, status=STATUS_KILLED)


def dumpjob_cmd(jq, io, args):
    import attr
    tasks_as_dicts = []
    jobid = _resolve_jobid(jq, args.jobid)
    job = jq.get_job(jobid)
    job = attr.asdict(job)
    tasks = jq.get_tasks(jobid)
    for task in tasks:
        t = attr.asdict(task)

        task_args = io.get_as_str(task.args)
        t['args_url'] = t['args']
        t['args'] = json.loads(task_args)
        tasks_as_dicts.append(t)
    print(json.dumps(dict(job=job, tasks=tasks_as_dicts), indent=2, sort_keys=True))


def version_cmd():
    print(kubeque.__version__)


def get_func_parameters(func):
    import inspect
    return inspect.getargspec(func)[0]


def main(argv=None):
    parse = argparse.ArgumentParser()
    parse.add_argument("--config", default=None)
    parse.add_argument("--debug", action="store_true", help="If set, debug messages will be output")
    subparser = parse.add_subparsers()

    parser = subparser.add_parser("validate", help="Run a series of tests to confirm the configuration is valid")
    parser.set_defaults(func=validate_cmd)

    parser = subparser.add_parser("sub", help="Submit a command (or batch of commands) for execution")
    parser.set_defaults(func=submit_cmd)
    parser.add_argument("--resources", "-r",
                        help="Specify the resources that are needed for running job. (ie: -r memory=5G,cpu=0.9) ")
    parser.add_argument("--file", "-f",
                        help="Job specification file (in JSON).  Only needed if command is not specified.")
    parser.add_argument("--push", "-u", action="append", default=[],
                        help="Path to a local file which should be uploaded to working directory of command before execution starts.  If filename starts with a '@' the file is interpreted as a list of files which need to be uploaded.")
    parser.add_argument("--image", "-i",
                        help="Name of docker image to run job within.  Defaults to value from kubeque config file.")
    parser.add_argument("--name", "-n", help="The name to assign to the job")
    parser.add_argument("--seq", type=int,
                        help="Parameterize the command by 'index'.  Submitting with --seq=10 will submit 10 commands with a parameter 'index' varied from 1 to 10")
    parser.add_argument("--loglive", action="store_true", help="If set, will write stdout from tasks to StackDriver logging")
    parser.add_argument("--params", "-p",
                        help="Parameterize the command by the rows in the specified CSV file.  If the CSV file has 5 rows, then 5 commands will be submitted.")
    parser.add_argument("--fetch", help="After run is complete, automatically download the results")
    parser.add_argument("--dryrun", action="store_true",
                        help="Don't actually submit the job but just print what would have been done")
    parser.add_argument("--skipkube", action="store_true", dest="skip_kube_submit",
                        help="Do all steps except submitting the job to kubernetes")
    parser.add_argument("--no-wait", action="store_false", dest="wait_for_completion",
                        help="Exit immediately after submission instead of waiting for job to complete")
    parser.add_argument("--results", action="append",
                        help="Wildcard to use to find results which will be uploaded.  (defaults to '*')  Can be specified multiple times",
                        default=None, dest="results_wildcards")
    parser.add_argument("--cd", help="The directory to change to before executing the command", default=".",
                        dest="working_dir")
    parser.add_argument("--local", help="Run the tasks inside of docker on the local machine", action="store_true")
    parser.add_argument("--clean", help="If the job id already exists, 'clean' it first to avoid an error about the job already existing", action="store_true")
    parser.add_argument("--rerun", help="If set, will download all of the files from previous execution of this job to worker before running", action="store_true")
    parser.add_argument("command", nargs=argparse.REMAINDER)

    parser = subparser.add_parser("addnodes", help="Add nodes to be used for executing a specific job")
    parser.set_defaults(func=addnodes_cmd)
    parser.add_argument("job_id", help="the job id used to determine which cluster node should be added to.")
    parser.add_argument("count", help="the number of worker nodes to add to the cluster", type=int)

    parser = subparser.add_parser("reset",
                                  help="Mark any 'claimed', 'killed' or 'failed' jobs as ready for execution again.  Useful largely only during debugging issues with job submission.")
    parser.set_defaults(func=reset_cmd)
    parser.add_argument("jobid_pattern")
    parser.add_argument("--owner")
    parser.add_argument("--resubmit", action="store_true")
    parser.add_argument("--all", action="store_true")

    parser = subparser.add_parser("listparams", help="Write to a csv file the parameters for each task")
    parser.set_defaults(func=list_params_cmd)
    parser.add_argument("jobid")
    parser.add_argument("filename", help="The filename to write the csv file containing the parameters")
    parser.add_argument("--incomplete", "-i",
                        help="By default, will list all parameters. If this flag is present, only those tasks which are not complete will be written to the csv",
                        action="store_true")
    parser.add_argument("--exitcode", "-e", help="Only include those tasks with this return code", type=int)
    parser.add_argument("--extra",
                        help="Add columns 'task_id' and 'exit_code' for each task",
                        action="store_true")

    #    parser = subparser.add_parser("retry", help="Resubmit any 'failed' jobs for execution again. (often after increasing memory required)")
    #    parser.set_defaults(func=retry_cmd)
    #    parser.add_argument("jobid_pattern")
    #    parser.add_argument("--resources", "-r", help="Update the resource requirements that should be used when re-running job. (ie: -r memory=5G,cpu=2) ")
    #    parser.add_argument("--owner", help="if specified, only tasks with this owner will be retried")
    #    parser.add_argument("--no-wait", action="store_false", dest="wait_for_completion", help="Exit immediately after submission instead of waiting for job to complete")

    parser = subparser.add_parser("dumpjob", help="Extract a json description of a submitted job")
    parser.set_defaults(func=dumpjob_cmd)
    parser.add_argument("jobid")

    parser = subparser.add_parser("status", help="Print the status for the tasks which make up the specified job")
    parser.set_defaults(func=status_cmd)
    parser.add_argument("--detailed", action="store_true", help="List attributes of each task")
    parser.add_argument("--failures", action="store_true", help="List attributes of each task (only for failures)")
    parser.add_argument("--wait", action="store_true",
                        help="If set, will periodically poll and print the status until all tasks terminate")
    parser.add_argument("--loglive", action="store_true", help="If set, will read stdout from tasks from StackDriver logging")
    parser.add_argument("jobid_pattern", nargs="?")

    parser = subparser.add_parser("saturate", help="Monitor the job, automatically adding nodes equal to the number of tasks, and re-add nodes when one is preempted")
    parser.set_defaults(func=saturate_cmd)
    parser.add_argument("jobid")
    parser.add_argument("--nodes", "-n", type=int, help="By default, saturate will try to create nodes equal to the number of tasks. This will allow you to override the number of nodes we will want to create")

    parser = subparser.add_parser("clean", help="Remove jobs which are not currently running from the database of jobs")
    parser.set_defaults(func=clean_cmd)
    parser.add_argument("jobid_pattern", nargs="?",
                        help="If specified will only attempt to remove jobs that match this pattern")
    parser.add_argument("--force", "-f", help="If set, will delete job regardless of whether it is running or not")

    parser = subparser.add_parser("kill", help="Terminate the specified job")
    parser.set_defaults(func=kill_cmd)
    parser.add_argument("--keepcluster", action="store_true",
                        help="If set will also terminate the nodes that the job is using to run. (This could impact other running jobs that use the same docker image)")
    parser.add_argument("jobid_pattern")

    parser = subparser.add_parser("fetch", help="Download results from a completed job")
    parser.set_defaults(func=fetch_cmd)
    parser.add_argument("jobid")
    parser.add_argument("--flat", action="store_true", help="Instead of writing each task into a seperate directory, write all files into the destination directory")
    parser.add_argument("--dest", help="The path to the directory where the results will be downloaded. If omitted a directory will be created with the job id")

    parser = subparser.add_parser("version", help="print the version and exit")
    parser.set_defaults(func=version_cmd)

    args = parse.parse_args(argv)

    if args.debug:
        logging.basicConfig(level=logging.DEBUG, format="%(asctime)s:%(levelname)s:%(name)s:%(message)s")
    else:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
        logging.getLogger("googleapiclient.discovery").setLevel(logging.WARN)

    if not hasattr(args, 'func'):
        parse.print_help()
        sys.exit(1)

    func_param_names = get_func_parameters(args.func)
    if len(set(["config", "jq", "io"]).intersection(func_param_names)) > 0:
        config_path = get_config_path(args.config)
        log.info("Using config: %s", config_path)
        config, jq, io, cluster = load_config(config_path)
    func_params = {}
    if "args" in func_param_names:
        func_params["args"] = args
    if "config" in func_param_names:
        func_params["config"] = config
    if "io" in func_param_names:
        func_params["io"] = io
    if "jq" in func_param_names:
        func_params["jq"] = jq
    if 'cluster' in func_param_names:
        func_params['cluster'] = cluster

    args.func(**func_params)


if __name__ == "__main__":
    main(sys.argv[1:])
