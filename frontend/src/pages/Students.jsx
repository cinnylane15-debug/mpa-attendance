import React, { useState, useEffect } from 'react';
import {
  Table, Button, Modal, Form, Input, Select, Tag, Upload, message, Space, Typography, Popconfirm, Image,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, UploadOutlined, SearchOutlined, CameraOutlined,
} from '@ant-design/icons';
import { apiGet, apiPost, apiPut, apiDelete, apiPostFile } from '../api';

const { Title } = Typography;
const { Option } = Select;

export default function Students() {
  const [students, setStudents] = useState([]);
  const [classes, setClasses] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingStudent, setEditingStudent] = useState(null);
  const [filterClass, setFilterClass] = useState(null);
  const [searchText, setSearchText] = useState('');
  const [form] = Form.useForm();

  const fetchStudents = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filterClass) params.append('class_id', filterClass);
      if (searchText) params.append('search', searchText);
      const data = await apiGet(`/students?${params.toString()}`);
      setStudents(Array.isArray(data) ? data : data?.items || []);
    } catch (err) {
      message.error('Failed to load students');
    } finally {
      setLoading(false);
    }
  };

  const fetchClasses = async () => {
    try {
      const data = await apiGet('/classes');
      setClasses(Array.isArray(data) ? data : data?.items || []);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    fetchStudents();
    fetchClasses();
  }, [filterClass]);

  const handleSearch = () => {
    fetchStudents();
  };

  const openAddModal = () => {
    setEditingStudent(null);
    form.resetFields();
    setModalOpen(true);
  };

  const openEditModal = (record) => {
    setEditingStudent(record);
    form.setFieldsValue({
      student_id: record.student_id,
      name: record.name,
      class_id: record.class_id || undefined,
      guardian_name: record.guardian_name || '',
      guardian_phone: record.guardian_phone || '',
      is_active: record.is_active,
    });
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (editingStudent) {
        const { student_id: _sid, ...updateData } = values;
        await apiPut(`/students/${editingStudent.id}`, updateData);
        message.success('Student updated');
      } else {
        await apiPost('/students', values);
        message.success('Student added');
      }
      setModalOpen(false);
      fetchStudents();
    } catch (err) {
      if (err.message) message.error(err.message);
    }
  };

  const handleDelete = async (id) => {
    try {
      await apiDelete(`/students/${id}`);
      message.success('Student deleted');
      fetchStudents();
    } catch (err) {
      message.error(err.message || 'Failed to delete student');
    }
  };

  const handlePhotoUpload = async (studentId, file) => {
    const formData = new FormData();
    formData.append('file', file);
    try {
      await apiPostFile(`/students/${studentId}/photo`, formData);
      message.success('Photo uploaded successfully');
      fetchStudents();
    } catch (err) {
      message.error(err.message || 'Failed to upload photo');
    }
    return false;
  };

  const columns = [
    {
      title: 'Student ID',
      dataIndex: 'student_id',
      key: 'student_id',
      width: 120,
    },
    {
      title: 'Photo',
      dataIndex: 'photo_path',
      key: 'photo',
      width: 70,
      render: (photo) => photo ? (
        <Image
          src={`/api/uploads/${photo}`}
          width={40}
          height={40}
          style={{ borderRadius: '50%', objectFit: 'cover' }}
          fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mN8/+F9PQAI8wNPvd7POQAAAABJRU5ErkJggg=="
        />
      ) : (
        <div style={{
          width: 40, height: 40, borderRadius: '50%', background: '#f0f0f0',
          display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#999',
        }}>
          <CameraOutlined />
        </div>
      ),
    },
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      sorter: (a, b) => a.name.localeCompare(b.name),
    },
    {
      title: 'Class',
      dataIndex: 'class_name',
      key: 'class_name',
      render: (text) => text || '-',
    },
    {
      title: 'Guardian',
      dataIndex: 'guardian_name',
      key: 'guardian_name',
      render: (text) => text || '-',
    },
    {
      title: 'Phone',
      dataIndex: 'guardian_phone',
      key: 'guardian_phone',
      render: (text) => text || '-',
    },
    {
      title: 'Face',
      dataIndex: 'has_face_embedding',
      key: 'face',
      width: 80,
      render: (has) => has ? <Tag color="green">Ready</Tag> : <Tag color="default">None</Tag>,
    },
    {
      title: 'Status',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 90,
      render: (active) => (
        <Tag color={active ? 'green' : 'red'}>
          {active ? 'Active' : 'Inactive'}
        </Tag>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 180,
      render: (_, record) => (
        <Space>
          <Upload
            showUploadList={false}
            beforeUpload={(file) => handlePhotoUpload(record.id, file)}
            accept="image/*"
          >
            <Button icon={<UploadOutlined />} size="small" title="Upload Photo" />
          </Upload>
          <Button
            icon={<EditOutlined />}
            size="small"
            onClick={() => openEditModal(record)}
          />
          <Popconfirm
            title="Delete this student?"
            onConfirm={() => handleDelete(record.id)}
            okText="Yes"
            cancelText="No"
          >
            <Button icon={<DeleteOutlined />} size="small" danger />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div className="page-header">
        <Title level={4} style={{ margin: 0 }}>Students</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openAddModal}>
          Add Student
        </Button>
      </div>

      <div className="filter-bar">
        <Select
          placeholder="Filter by class"
          allowClear
          style={{ width: 200 }}
          value={filterClass}
          onChange={(val) => setFilterClass(val)}
        >
          {classes.map((cls) => (
            <Option key={cls.id} value={cls.id}>{cls.name}</Option>
          ))}
        </Select>
        <Input.Search
          placeholder="Search students..."
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          onSearch={handleSearch}
          style={{ width: 250 }}
          enterButton={<SearchOutlined />}
        />
      </div>

      <Table
        columns={columns}
        dataSource={students}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (total) => `Total: ${total} students` }}
      />

      <Modal
        title={editingStudent ? 'Edit Student' : 'Add Student'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        okText={editingStudent ? 'Update' : 'Add'}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="student_id"
            label="Student ID"
            rules={[{ required: true, message: 'Student ID is required' }]}
          >
            <Input placeholder="e.g., STU001" disabled={!!editingStudent} />
          </Form.Item>
          <Form.Item
            name="name"
            label="Full Name"
            rules={[{ required: true, message: 'Name is required' }]}
          >
            <Input placeholder="Student full name" />
          </Form.Item>
          <Form.Item name="class_id" label="Class">
            <Select placeholder="Select class" allowClear>
              {classes.map((cls) => (
                <Option key={cls.id} value={cls.id}>{cls.name}</Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="guardian_name" label="Guardian Name">
            <Input placeholder="Parent/Guardian name" />
          </Form.Item>
          <Form.Item name="guardian_phone" label="Guardian Phone">
            <Input placeholder="Phone number" />
          </Form.Item>
          {editingStudent && (
            <Form.Item name="is_active" label="Status">
              <Select>
                <Option value={true}>Active</Option>
                <Option value={false}>Inactive</Option>
              </Select>
            </Form.Item>
          )}
        </Form>
      </Modal>
    </div>
  );
}
