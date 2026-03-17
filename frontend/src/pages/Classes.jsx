import React, { useState, useEffect } from 'react';
import {
  Table, Button, Modal, Form, Input, Select, Tag, message, Space, Typography, Popconfirm, Card, List,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, TeamOutlined } from '@ant-design/icons';
import { apiGet, apiPost, apiPut, apiDelete } from '../api';

const { Title, Text } = Typography;
const { Option } = Select;

export default function Classes() {
  const [classes, setClasses] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingClass, setEditingClass] = useState(null);
  const [studentsModal, setStudentsModal] = useState(false);
  const [selectedClass, setSelectedClass] = useState(null);
  const [classStudents, setClassStudents] = useState([]);
  const [studentsLoading, setStudentsLoading] = useState(false);
  const [form] = Form.useForm();

  const fetchClasses = async () => {
    setLoading(true);
    try {
      const data = await apiGet('/classes');
      setClasses(Array.isArray(data) ? data : data?.items || []);
    } catch (err) {
      message.error('Failed to load classes');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchClasses();
  }, []);

  const openAddModal = () => {
    setEditingClass(null);
    form.resetFields();
    setModalOpen(true);
  };

  const openEditModal = (record) => {
    setEditingClass(record);
    form.setFieldsValue({
      name: record.name,
      section: record.section || '',
      grade: record.grade || '',
    });
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (editingClass) {
        await apiPut(`/classes/${editingClass.id}`, values);
        message.success('Class updated');
      } else {
        await apiPost('/classes', values);
        message.success('Class added');
      }
      setModalOpen(false);
      fetchClasses();
    } catch (err) {
      if (err.message) message.error(err.message);
    }
  };

  const handleDelete = async (id) => {
    try {
      await apiDelete(`/classes/${id}`);
      message.success('Class deleted');
      fetchClasses();
    } catch (err) {
      message.error(err.message || 'Failed to delete class');
    }
  };

  const viewStudents = async (record) => {
    setSelectedClass(record);
    setStudentsLoading(true);
    setStudentsModal(true);
    try {
      const data = await apiGet(`/students?class_id=${record.id}`);
      setClassStudents(Array.isArray(data) ? data : data?.items || []);
    } catch {
      setClassStudents([]);
    } finally {
      setStudentsLoading(false);
    }
  };

  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      sorter: (a, b) => a.name.localeCompare(b.name),
    },
    {
      title: 'Section',
      dataIndex: 'section',
      key: 'section',
      render: (text) => text || '-',
    },
    {
      title: 'Grade',
      dataIndex: 'grade',
      key: 'grade',
      render: (text) => text || '-',
    },
    {
      title: 'Students',
      dataIndex: 'student_count',
      key: 'student_count',
      render: (count) => (
        <Tag icon={<TeamOutlined />} color="blue">
          {count ?? 0}
        </Tag>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 200,
      render: (_, record) => (
        <Space>
          <Button
            icon={<TeamOutlined />}
            size="small"
            onClick={() => viewStudents(record)}
          >
            Students
          </Button>
          <Button
            icon={<EditOutlined />}
            size="small"
            onClick={() => openEditModal(record)}
          />
          <Popconfirm
            title="Delete this class? All students in this class will be unassigned."
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

  const studentColumns = [
    { title: 'Student ID', dataIndex: 'student_id', key: 'student_id' },
    { title: 'Name', dataIndex: 'name', key: 'name' },
    {
      title: 'Status',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (active) => <Tag color={active ? 'green' : 'red'}>{active ? 'Active' : 'Inactive'}</Tag>,
    },
  ];

  return (
    <div>
      <div className="page-header">
        <Title level={4} style={{ margin: 0 }}>Classes</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openAddModal}>
          Add Class
        </Button>
      </div>

      <Table
        columns={columns}
        dataSource={classes}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 20, showTotal: (total) => `Total: ${total} classes` }}
      />

      <Modal
        title={editingClass ? 'Edit Class' : 'Add Class'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        okText={editingClass ? 'Update' : 'Add'}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="Class Name"
            rules={[{ required: true, message: 'Class name is required' }]}
          >
            <Input placeholder="e.g., Grade 5 - A" />
          </Form.Item>
          <Form.Item name="section" label="Section">
            <Input placeholder="e.g., A, B, C" />
          </Form.Item>
          <Form.Item name="grade" label="Grade">
            <Input placeholder="e.g., 5, 6, 7" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`Students in ${selectedClass?.name || ''}`}
        open={studentsModal}
        onCancel={() => setStudentsModal(false)}
        footer={null}
        width={600}
      >
        <Table
          columns={studentColumns}
          dataSource={classStudents}
          rowKey="id"
          loading={studentsLoading}
          pagination={false}
          size="small"
          locale={{ emptyText: 'No students in this class' }}
        />
      </Modal>
    </div>
  );
}
