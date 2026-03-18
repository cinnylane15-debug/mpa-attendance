import React, { useState, useEffect } from 'react';
import {
  Table, Button, Modal, Form, Input, Select, Tag, Upload, message, Space, Typography, Popconfirm, Image, Badge, List,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, UploadOutlined, SearchOutlined, CameraOutlined, PictureOutlined,
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

  // Photo management modal
  const [photosModalOpen, setPhotosModalOpen] = useState(false);
  const [photosStudent, setPhotosStudent] = useState(null);
  const [photos, setPhotos] = useState([]);
  const [photosLoading, setPhotosLoading] = useState(false);

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
      // If photos modal is open for this student, refresh photos
      if (photosStudent && photosStudent.id === studentId) {
        fetchPhotos(studentId);
      }
    } catch (err) {
      message.error(err.message || 'Failed to upload photo');
    }
    return false;
  };

  const fetchPhotos = async (studentId) => {
    setPhotosLoading(true);
    try {
      const data = await apiGet(`/students/${studentId}/photos`);
      setPhotos(Array.isArray(data) ? data : []);
    } catch (err) {
      message.error('Failed to load photos');
    } finally {
      setPhotosLoading(false);
    }
  };

  const openPhotosModal = (record) => {
    setPhotosStudent(record);
    setPhotosModalOpen(true);
    fetchPhotos(record.id);
  };

  const handleDeletePhoto = async (photoId) => {
    if (!photosStudent) return;
    try {
      await apiDelete(`/students/${photosStudent.id}/photos/${photoId}`);
      message.success('Photo deleted');
      fetchPhotos(photosStudent.id);
      fetchStudents();
    } catch (err) {
      message.error(err.message || 'Failed to delete photo');
    }
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
          src={`/uploads/${photo}`}
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
      width: 100,
      render: (has, record) => has ? (
        <Tag color="green" style={{ cursor: 'pointer' }} onClick={() => openPhotosModal(record)}>
          Ready ({record.photo_count || 1})
        </Tag>
      ) : <Tag color="default">None</Tag>,
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
      width: 220,
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
            icon={<PictureOutlined />}
            size="small"
            onClick={() => openPhotosModal(record)}
            title="Manage Photos"
          />
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

      {/* Photos Management Modal */}
      <Modal
        title={`Photos: ${photosStudent?.name || ''}`}
        open={photosModalOpen}
        onCancel={() => { setPhotosModalOpen(false); setPhotosStudent(null); setPhotos([]); }}
        footer={[
          <Upload
            key="upload"
            showUploadList={false}
            beforeUpload={(file) => photosStudent && handlePhotoUpload(photosStudent.id, file)}
            accept="image/*"
          >
            <Button type="primary" icon={<UploadOutlined />}>Add Photo</Button>
          </Upload>,
        ]}
        width={600}
      >
        {photos.length === 0 && !photosLoading ? (
          <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
            <CameraOutlined style={{ fontSize: 48, marginBottom: 16 }} />
            <p>No photos uploaded yet. Add photos for better face recognition accuracy.</p>
          </div>
        ) : (
          <List
            loading={photosLoading}
            grid={{ gutter: 16, column: 3 }}
            dataSource={photos}
            renderItem={(photo) => (
              <List.Item>
                <div style={{ position: 'relative', textAlign: 'center' }}>
                  <Image
                    src={`/uploads/${photo.photo_path}`}
                    width={150}
                    height={150}
                    style={{ objectFit: 'cover', borderRadius: 8 }}
                    fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mN8/+F9PQAI8wNPvd7POQAAAABJRU5ErkJggg=="
                  />
                  <div style={{ marginTop: 4 }}>
                    <Popconfirm
                      title="Delete this photo?"
                      onConfirm={() => handleDeletePhoto(photo.id)}
                      okText="Yes"
                      cancelText="No"
                    >
                      <Button size="small" danger icon={<DeleteOutlined />}>Remove</Button>
                    </Popconfirm>
                  </div>
                </div>
              </List.Item>
            )}
          />
        )}
        <div style={{ marginTop: 12, color: '#888', fontSize: 12 }}>
          Upload multiple photos from different angles for better recognition accuracy.
        </div>
      </Modal>
    </div>
  );
}
