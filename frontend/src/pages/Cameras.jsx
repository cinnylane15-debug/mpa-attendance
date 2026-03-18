import React, { useState, useEffect } from 'react';
import {
  Card, Button, Modal, Form, Input, Select, Tag, message, Space, Typography, Popconfirm, Row, Col, Badge,
} from 'antd';
import {
  PlusOutlined, DeleteOutlined, PlayCircleOutlined, PauseCircleOutlined,
  ApiOutlined, CameraOutlined, EnvironmentOutlined,
} from '@ant-design/icons';
import { apiGet, apiPost, apiPut, apiDelete } from '../api';

const { Title, Text, Paragraph } = Typography;
const { Option } = Select;

function maskRtspUrl(url) {
  if (!url) return '';
  try {
    const parsed = new URL(url);
    if (parsed.password) {
      parsed.password = '****';
    }
    return parsed.toString();
  } catch {
    return url.replace(/:([^@/]+)@/, ':****@');
  }
}

export default function Cameras() {
  const [cameras, setCameras] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();

  const fetchCameras = async () => {
    setLoading(true);
    try {
      const data = await apiGet('/cameras');
      setCameras(Array.isArray(data) ? data : data?.items || []);
    } catch (err) {
      message.error('Failed to load cameras');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCameras();
  }, []);

  const openAddModal = () => {
    form.resetFields();
    form.setFieldsValue({ direction: 'entry', is_active: true, capture_mode: 'snapshot' });
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      await apiPost('/cameras', values);
      message.success('Camera added');
      setModalOpen(false);
      fetchCameras();
    } catch (err) {
      if (err.message) message.error(err.message);
    }
  };

  const handleDelete = async (id) => {
    try {
      await apiDelete(`/cameras/${id}`);
      message.success('Camera deleted');
      fetchCameras();
    } catch (err) {
      message.error(err.message || 'Failed to delete camera');
    }
  };

  const handleToggle = async (camera) => {
    try {
      await apiPut(`/cameras/${camera.id}`, { is_active: !camera.is_active });
      message.success(`Camera ${camera.is_active ? 'stopped' : 'started'}`);
      fetchCameras();
    } catch (err) {
      message.error(err.message || 'Failed to toggle camera');
    }
  };

  const handleTestConnection = async (id) => {
    try {
      const result = await apiPost(`/cameras/${id}/test`, {});
      if (result?.success || result?.status === 'ok') {
        message.success('Connection successful');
      } else {
        message.warning(result?.message || 'Connection test completed');
      }
    } catch (err) {
      message.error(err.message || 'Connection test failed');
    }
  };

  return (
    <div>
      <div className="page-header">
        <Title level={4} style={{ margin: 0 }}>Cameras</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openAddModal}>
          Add Camera
        </Button>
      </div>

      <Row gutter={[16, 16]}>
        {cameras.map((camera) => (
          <Col xs={24} sm={12} lg={8} key={camera.id}>
            <Card
              className="camera-card"
              title={
                <Space>
                  <CameraOutlined />
                  <span>{camera.name}</span>
                </Space>
              }
              extra={
                <Badge
                  status={camera.is_active ? 'success' : 'error'}
                  text={camera.is_active ? 'Active' : 'Inactive'}
                />
              }
            >
              <div style={{ marginBottom: 12 }}>
                <Space direction="vertical" style={{ width: '100%' }}>
                  <div>
                    <EnvironmentOutlined style={{ marginRight: 8, color: '#888' }} />
                    <Text type="secondary">{camera.location || 'No location set'}</Text>
                  </div>
                  <div>
                    <Text type="secondary" style={{ fontSize: 12 }}>RTSP URL:</Text>
                    <Paragraph
                      copyable={{ text: camera.rtsp_url }}
                      style={{ fontSize: 12, margin: '4px 0 0 0', wordBreak: 'break-all' }}
                      ellipsis={{ rows: 2 }}
                    >
                      {maskRtspUrl(camera.rtsp_url)}
                    </Paragraph>
                  </div>
                  <div>
                    <Tag color={camera.direction === 'entry' ? 'green' : 'orange'}>
                      {camera.direction === 'entry' ? 'Entry' : 'Exit'}
                    </Tag>
                    <Tag color={camera.capture_mode === 'snapshot' ? 'blue' : 'purple'}>
                      {camera.capture_mode === 'snapshot' ? 'HTTP Snapshot' : 'RTSP Stream'}
                    </Tag>
                  </div>
                </Space>
              </div>
              <Space wrap>
                <Button
                  size="small"
                  icon={camera.is_active ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
                  onClick={() => handleToggle(camera)}
                >
                  {camera.is_active ? 'Stop' : 'Start'}
                </Button>
                <Button
                  size="small"
                  icon={<ApiOutlined />}
                  onClick={() => handleTestConnection(camera.id)}
                >
                  Test
                </Button>
                <Popconfirm
                  title="Delete this camera?"
                  onConfirm={() => handleDelete(camera.id)}
                  okText="Yes"
                  cancelText="No"
                >
                  <Button size="small" icon={<DeleteOutlined />} danger />
                </Popconfirm>
              </Space>
            </Card>
          </Col>
        ))}
        {cameras.length === 0 && !loading && (
          <Col span={24}>
            <Card>
              <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
                <CameraOutlined style={{ fontSize: 48, marginBottom: 16 }} />
                <div>No cameras configured. Click "Add Camera" to get started.</div>
              </div>
            </Card>
          </Col>
        )}
      </Row>

      <Modal
        title="Add Camera"
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        okText="Add"
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="Camera Name"
            rules={[{ required: true, message: 'Camera name is required' }]}
          >
            <Input placeholder="e.g., Main Gate Camera" />
          </Form.Item>
          <Form.Item name="location" label="Location">
            <Input placeholder="e.g., Front Entrance" />
          </Form.Item>
          <Form.Item
            name="rtsp_url"
            label="RTSP URL"
            rules={[{ required: true, message: 'RTSP URL is required' }]}
            extra="Dahua format: rtsp://admin:password@192.168.1.108:554/cam/realmonitor?channel=1&subtype=0"
          >
            <Input placeholder="rtsp://username:password@ip:port/path" />
          </Form.Item>
          <Form.Item
            name="direction"
            label="Direction"
            rules={[{ required: true }]}
          >
            <Select>
              <Option value="entry">Entry</Option>
              <Option value="exit">Exit</Option>
            </Select>
          </Form.Item>
          <Form.Item
            name="capture_mode"
            label="Capture Mode"
            rules={[{ required: true }]}
            extra="Snapshot is recommended — grabs images via HTTP, more reliable than RTSP streaming"
          >
            <Select>
              <Option value="snapshot">HTTP Snapshot (recommended)</Option>
              <Option value="rtsp">RTSP Stream</Option>
            </Select>
          </Form.Item>
          <Form.Item
            name="snapshot_url"
            label="Snapshot URL (optional)"
            extra="Auto-derived from RTSP URL if left blank. Format: http://admin:pass@ip/cgi-bin/snapshot.cgi?channel=1"
          >
            <Input placeholder="Leave blank to auto-detect from RTSP URL" />
          </Form.Item>
          <Form.Item name="is_active" label="Active" valuePropName="value">
            <Select>
              <Option value={true}>Yes</Option>
              <Option value={false}>No</Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
