// Code generated by protoc-gen-go. DO NOT EDIT.
// source: sparklespray.proto

package sparklespray

import proto "github.com/golang/protobuf/proto"
import fmt "fmt"
import math "math"

import (
	context "golang.org/x/net/context"
	grpc "google.golang.org/grpc"
)

// Reference imports to suppress errors if they are not otherwise used.
var _ = proto.Marshal
var _ = fmt.Errorf
var _ = math.Inf

// This is a compile-time assertion to ensure that this generated file
// is compatible with the proto package it is being compiled against.
// A compilation error at this line likely means your copy of the
// proto package needs to be updated.
const _ = proto.ProtoPackageIsVersion2 // please upgrade the proto package

// The request message containing the user's name.
type ReadOutputRequest struct {
	TaskId               string   `protobuf:"bytes,1,opt,name=taskId,proto3" json:"taskId,omitempty"`
	Size                 int32    `protobuf:"varint,2,opt,name=size,proto3" json:"size,omitempty"`
	Offset               int64    `protobuf:"varint,3,opt,name=offset,proto3" json:"offset,omitempty"`
	XXX_NoUnkeyedLiteral struct{} `json:"-"`
	XXX_unrecognized     []byte   `json:"-"`
	XXX_sizecache        int32    `json:"-"`
}

func (m *ReadOutputRequest) Reset()         { *m = ReadOutputRequest{} }
func (m *ReadOutputRequest) String() string { return proto.CompactTextString(m) }
func (*ReadOutputRequest) ProtoMessage()    {}
func (*ReadOutputRequest) Descriptor() ([]byte, []int) {
	return fileDescriptor_sparklespray_ed3d994d0d3b02d0, []int{0}
}
func (m *ReadOutputRequest) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_ReadOutputRequest.Unmarshal(m, b)
}
func (m *ReadOutputRequest) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_ReadOutputRequest.Marshal(b, m, deterministic)
}
func (dst *ReadOutputRequest) XXX_Merge(src proto.Message) {
	xxx_messageInfo_ReadOutputRequest.Merge(dst, src)
}
func (m *ReadOutputRequest) XXX_Size() int {
	return xxx_messageInfo_ReadOutputRequest.Size(m)
}
func (m *ReadOutputRequest) XXX_DiscardUnknown() {
	xxx_messageInfo_ReadOutputRequest.DiscardUnknown(m)
}

var xxx_messageInfo_ReadOutputRequest proto.InternalMessageInfo

func (m *ReadOutputRequest) GetTaskId() string {
	if m != nil {
		return m.TaskId
	}
	return ""
}

func (m *ReadOutputRequest) GetSize() int32 {
	if m != nil {
		return m.Size
	}
	return 0
}

func (m *ReadOutputRequest) GetOffset() int64 {
	if m != nil {
		return m.Offset
	}
	return 0
}

// The response message containing the greetings
type ReadOutputReply struct {
	Data                 []byte   `protobuf:"bytes,1,opt,name=data,proto3" json:"data,omitempty"`
	EndOfFile            bool     `protobuf:"varint,2,opt,name=endOfFile,proto3" json:"endOfFile,omitempty"`
	XXX_NoUnkeyedLiteral struct{} `json:"-"`
	XXX_unrecognized     []byte   `json:"-"`
	XXX_sizecache        int32    `json:"-"`
}

func (m *ReadOutputReply) Reset()         { *m = ReadOutputReply{} }
func (m *ReadOutputReply) String() string { return proto.CompactTextString(m) }
func (*ReadOutputReply) ProtoMessage()    {}
func (*ReadOutputReply) Descriptor() ([]byte, []int) {
	return fileDescriptor_sparklespray_ed3d994d0d3b02d0, []int{1}
}
func (m *ReadOutputReply) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_ReadOutputReply.Unmarshal(m, b)
}
func (m *ReadOutputReply) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_ReadOutputReply.Marshal(b, m, deterministic)
}
func (dst *ReadOutputReply) XXX_Merge(src proto.Message) {
	xxx_messageInfo_ReadOutputReply.Merge(dst, src)
}
func (m *ReadOutputReply) XXX_Size() int {
	return xxx_messageInfo_ReadOutputReply.Size(m)
}
func (m *ReadOutputReply) XXX_DiscardUnknown() {
	xxx_messageInfo_ReadOutputReply.DiscardUnknown(m)
}

var xxx_messageInfo_ReadOutputReply proto.InternalMessageInfo

func (m *ReadOutputReply) GetData() []byte {
	if m != nil {
		return m.Data
	}
	return nil
}

func (m *ReadOutputReply) GetEndOfFile() bool {
	if m != nil {
		return m.EndOfFile
	}
	return false
}

func init() {
	proto.RegisterType((*ReadOutputRequest)(nil), "ReadOutputRequest")
	proto.RegisterType((*ReadOutputReply)(nil), "ReadOutputReply")
}

// Reference imports to suppress errors if they are not otherwise used.
var _ context.Context
var _ grpc.ClientConn

// This is a compile-time assertion to ensure that this generated file
// is compatible with the grpc package it is being compiled against.
const _ = grpc.SupportPackageIsVersion4

// MonitorClient is the client API for Monitor service.
//
// For semantics around ctx use and closing/ending streaming RPCs, please refer to https://godoc.org/google.golang.org/grpc#ClientConn.NewStream.
type MonitorClient interface {
	// Sends a greeting
	ReadOutput(ctx context.Context, in *ReadOutputRequest, opts ...grpc.CallOption) (*ReadOutputReply, error)
}

type monitorClient struct {
	cc *grpc.ClientConn
}

func NewMonitorClient(cc *grpc.ClientConn) MonitorClient {
	return &monitorClient{cc}
}

func (c *monitorClient) ReadOutput(ctx context.Context, in *ReadOutputRequest, opts ...grpc.CallOption) (*ReadOutputReply, error) {
	out := new(ReadOutputReply)
	err := c.cc.Invoke(ctx, "/Monitor/ReadOutput", in, out, opts...)
	if err != nil {
		return nil, err
	}
	return out, nil
}

// MonitorServer is the server API for Monitor service.
type MonitorServer interface {
	// Sends a greeting
	ReadOutput(context.Context, *ReadOutputRequest) (*ReadOutputReply, error)
}

func RegisterMonitorServer(s *grpc.Server, srv MonitorServer) {
	s.RegisterService(&_Monitor_serviceDesc, srv)
}

func _Monitor_ReadOutput_Handler(srv interface{}, ctx context.Context, dec func(interface{}) error, interceptor grpc.UnaryServerInterceptor) (interface{}, error) {
	in := new(ReadOutputRequest)
	if err := dec(in); err != nil {
		return nil, err
	}
	if interceptor == nil {
		return srv.(MonitorServer).ReadOutput(ctx, in)
	}
	info := &grpc.UnaryServerInfo{
		Server:     srv,
		FullMethod: "/Monitor/ReadOutput",
	}
	handler := func(ctx context.Context, req interface{}) (interface{}, error) {
		return srv.(MonitorServer).ReadOutput(ctx, req.(*ReadOutputRequest))
	}
	return interceptor(ctx, in, info, handler)
}

var _Monitor_serviceDesc = grpc.ServiceDesc{
	ServiceName: "Monitor",
	HandlerType: (*MonitorServer)(nil),
	Methods: []grpc.MethodDesc{
		{
			MethodName: "ReadOutput",
			Handler:    _Monitor_ReadOutput_Handler,
		},
	},
	Streams:  []grpc.StreamDesc{},
	Metadata: "sparklespray.proto",
}

func init() { proto.RegisterFile("sparklespray.proto", fileDescriptor_sparklespray_ed3d994d0d3b02d0) }

var fileDescriptor_sparklespray_ed3d994d0d3b02d0 = []byte{
	// 191 bytes of a gzipped FileDescriptorProto
	0x1f, 0x8b, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0xff, 0xe2, 0x12, 0x2a, 0x2e, 0x48, 0x2c,
	0xca, 0xce, 0x49, 0x2d, 0x2e, 0x28, 0x4a, 0xac, 0xd4, 0x2b, 0x28, 0xca, 0x2f, 0xc9, 0x57, 0x0a,
	0xe7, 0x12, 0x0c, 0x4a, 0x4d, 0x4c, 0xf1, 0x2f, 0x2d, 0x29, 0x28, 0x2d, 0x09, 0x4a, 0x2d, 0x2c,
	0x4d, 0x2d, 0x2e, 0x11, 0x12, 0xe3, 0x62, 0x2b, 0x49, 0x2c, 0xce, 0xf6, 0x4c, 0x91, 0x60, 0x54,
	0x60, 0xd4, 0xe0, 0x0c, 0x82, 0xf2, 0x84, 0x84, 0xb8, 0x58, 0x8a, 0x33, 0xab, 0x52, 0x25, 0x98,
	0x14, 0x18, 0x35, 0x58, 0x83, 0xc0, 0x6c, 0x90, 0xda, 0xfc, 0xb4, 0xb4, 0xe2, 0xd4, 0x12, 0x09,
	0x66, 0x05, 0x46, 0x0d, 0xe6, 0x20, 0x28, 0x4f, 0xc9, 0x99, 0x8b, 0x1f, 0xd9, 0xe0, 0x82, 0x9c,
	0x4a, 0x90, 0xf6, 0x94, 0xc4, 0x92, 0x44, 0xb0, 0xa1, 0x3c, 0x41, 0x60, 0xb6, 0x90, 0x0c, 0x17,
	0x67, 0x6a, 0x5e, 0x8a, 0x7f, 0x9a, 0x5b, 0x66, 0x0e, 0xc4, 0x5c, 0x8e, 0x20, 0x84, 0x80, 0x91,
	0x3d, 0x17, 0xbb, 0x6f, 0x7e, 0x5e, 0x66, 0x49, 0x7e, 0x91, 0x90, 0x09, 0x17, 0x17, 0xc2, 0x3c,
	0x21, 0x21, 0x3d, 0x0c, 0x57, 0x4b, 0x09, 0xe8, 0xa1, 0x59, 0xa8, 0xc4, 0x90, 0xc4, 0x06, 0xf6,
	0xa5, 0x31, 0x20, 0x00, 0x00, 0xff, 0xff, 0x0a, 0xe8, 0xd4, 0xdc, 0xfb, 0x00, 0x00, 0x00,
}
