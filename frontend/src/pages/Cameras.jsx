import React, { useState, useEffect } from 'react';
import {
  Card, Button, Modal, Form, Input, Select, Tag, message, Space, Typography, Popconfirm,
  Row, Col, Badge, Drawer, List, Timeline, Spin,
} from 'antd';
import {
  PlusOutlined, DeleteOutlined, PlayCircleOutlined, PauseCircleOutlined,
  ApiOutlined, CameraOutlined, EnvironmentOutlined, EditOutlined,
  FileTextOutlined, CheckCircleOutlined, QuestionCircleOutlined, ReloadOutlined,
} from '@ant-design/icons';
import { apiGet, apiPost, apiPut, apiDelete } from '../api';
import dayjs from 'dayjs';

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

function LiveSnapshot({ cameraId }) {
  const [src, setSrc] = React.useState(null);
  const [error, setError] = React.useState(false);
  const [refreshKey, setRefreshKey] = React.useState(0);

  React.useEffect(() => {
    let cancelled = false;
    const token = localStorage.getItem('token');
    fetch(`/api/cameras/${cameraId}/snapshot/`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((r) => {
        if (!r.ok) throw new Error('Failed');
        return r.blob();
      })
      .then((blob) => {
        if (!cancelled) {
          setSrc(URL.createObjectURL(blob));
          setError(false);
        }
      })
      .catch(() => { if (!cancelled) setError(true); });
    return () => { cancelled = true; };
  }, [cameraId, refreshKey]);

  return (
    <Card
      size="small"
      title="Live View"
      extra={
        <Button size="small" icon={<ReloadOutlined />} onClick={() => setRefreshKey((k) => k + 1)}>
          Refresh
        </Button>
      }
      style={{ marginBottom: 16 }}
    >
      {src ? (
        <img src={src} alt="Live snapshot" style={{ width: '100%', borderRadius: 4 }} />
      ) : error ? (
        <div style={{ textAlign: 'center', padding: 20, color: '#999' }}>
          Could not load snapshot
        </div>
      ) : (
        <div style={{ textAlign: 'center', padding: 20 }}><Spin /></div>
      )}
    </Card>
  );
}

export default function Cameras() {
  const [cameras, setCameras] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingCamera, setEditingCamera] = useState(null);
  const [logsDrawer, setLogsDrawer] = useState(null); // camera id
  const [logs, setLogs] = useState(null);
  const [logsLoading, setLogsLoading] = useState(false);
  const [snapshotKey, setSnapshotKey] = useState(0);
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
    setEditingCamera(null);
    form.resetFields();
    form.setFieldsValue({ direction: 'entry', is_active: true, capture_mode: 'snapshot' });
    setModalOpen(true);
  };

  const openEditModal = (camera) => {
    setEditingCamera(camera);
    form.setFieldsValue({
      name: camera.name,
      location: camera.location || '',
      rtsp_url: camera.rtsp_url,
      direction: camera.direction,
      capture_mode: camera.capture_mode || 'snapshot',
      snapshot_url: camera.snapshot_url || '',
      is_active: camera.is_active,
    });
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (!values.snapshot_url) delete values.snapshot_url;
      if (editingCamera) {
        await apiPut(`/cameras/${editingCamera.id}`, values);
        message.success('Camera updated');
      } else {
        await apiPost('/cameras', values);
        message.success('Camera added');
      }
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
      if (camera.is_active) {
        await apiPost(`/cameras/${camera.id}/stop`, {});
        await apiPut(`/cameras/${camera.id}`, { is_active: false });
        message.success('Camera stopped');
      } else {
        await apiPut(`/cameras/${camera.id}`, { is_active: true });
        await apiPost(`/cameras/${camera.id}/start`, {});
        message.success('Camera started');
      }
      fetchCameras();
    } catch (err) {
      message.error(err.message || 'Failed to toggle camera');
    }
  };

  const handleTestConnection = async (id) => {
    try {
      const result = await apiPost(`/cameras/${id}/test`, {});
      if (result?.success) {
        message.success(result.message || 'Connection successful');
      } else {
        message.warning(result?.message || 'Connection test failed');
      }
    } catch (err) {
      message.error(err.message || 'Connection test failed');
    }
  };

  const openLogs = async (camera) => {
    setLogsDrawer(camera);
    setLogsLoading(true);
    setLogs(null);
    try {
      const data = await apiGet(`/cameras/${camera.id}/logs?limit=30`);
      setLogs(data);
    } catch (err) {
      message.error('Failed to load camera logs');
    } finally {
      setLogsLoading(false);
    }
  };

  const cameraForm = (
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
        extra="Dahua format: rtsp://admin:password@192.168.1.9:554/cam/realmonitor?channel=1&subtype=0"
      >
        <Input placeholder="rtsp://username:password@ip:port/path" />
      </Form.Item>
      <Row gutter={16}>
        <Col span={12}>
          <Form.Item name="direction" label="Direction" rules={[{ required: true }]}>
            <Select>
              <Option value="entry">Entry</Option>
              <Option value="exit">Exit</Option>
            </Select>
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item
            name="capture_mode"
            label="Capture Mode"
            rules={[{ required: true }]}
          >
            <Select>
              <Option value="snapshot">HTTP Snapshot</Option>
              <Option value="rtsp">RTSP Stream</Option>
            </Select>
          </Form.Item>
        </Col>
      </Row>
      <Form.Item
        name="snapshot_url"
        label="Snapshot URL (optional)"
        extra="Leave blank to auto-detect from RTSP URL"
      >
        <Input placeholder="http://admin:pass@ip/cgi-bin/snapshot.cgi?channel=1" />
      </Form.Item>
      <Form.Item name="is_active" label="Active" valuePropName="value">
        <Select>
          <Option value={true}>Yes</Option>
          <Option value={false}>No</Option>
        </Select>
      </Form.Item>
    </Form>
  );

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
                <Button
                  size="small"
                  icon={<EditOutlined />}
                  onClick={() => openEditModal(camera)}
                >
                  Edit
                </Button>
                <Button
                  size="small"
                  icon={<FileTextOutlined />}
                  onClick={() => openLogs(camera)}
                >
                  Logs
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

      {/* Add / Edit Modal */}
      <Modal
        title={editingCamera ? 'Edit Camera' : 'Add Camera'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        okText={editingCamera ? 'Update' : 'Add'}
        destroyOnClose
      >
        {cameraForm}
      </Modal>

      {/* Logs Drawer */}
      <Drawer
        title={logsDrawer ? `Logs: ${logsDrawer.name}` : 'Camera Logs'}
        open={!!logsDrawer}
        onClose={() => { setLogsDrawer(null); setLogs(null); }}
        width={480}
      >
        {logsLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
        ) : logs ? (
          <div>
            <div style={{ marginBottom: 16 }}>
              <Space>
                <Badge status={logs.is_running ? 'success' : 'error'} text={logs.is_running ? 'Worker Running' : 'Worker Stopped'} />
                <Tag>{logs.capture_mode === 'snapshot' ? 'Snapshot Mode' : 'RTSP Mode'}</Tag>
              </Space>
            </div>

            {/* Live Snapshot */}
            {logsDrawer && <LiveSnapshot cameraId={logsDrawer.id} />}
            {logs.logs && logs.logs.length > 0 ? (
              <Timeline
                items={logs.logs.map((log, i) => ({
                  color: log.type === 'attendance' ? 'green' : 'orange',
                  dot: log.type === 'attendance' ? <CheckCircleOutlined /> : <QuestionCircleOutlined />,
                  children: (
                    <div key={i}>
                      <div>
                        {log.type === 'attendance' ? (
                          <Space>
                            <Text strong>{log.student_name}</Text>
                            <Text type="secondary">({log.student_code})</Text>
                            <Tag color={log.status === 'present' ? 'green' : log.status === 'late' ? 'orange' : 'red'} style={{ fontSize: 11 }}>
                              {log.status}
                            </Tag>
                          </Space>
                        ) : (
                          <Space>
                            <Text type="warning">Unknown face</Text>
                            {log.confidence != null && (
                              <Tag color="red" style={{ fontSize: 11 }}>
                                {(log.confidence * 100).toFixed(0)}% match
                              </Tag>
                            )}
                            {log.is_resolved && <Tag color="green" style={{ fontSize: 11 }}>Resolved</Tag>}
                          </Space>
                        )}
                      </div>
                      {log.confidence != null && log.type === 'attendance' && (
                        <Text type="secondary" style={{ fontSize: 11 }}>Confidence: {(log.confidence * 100).toFixed(1)}%</Text>
                      )}
                      <div>
                        <Text type="secondary" style={{ fontSize: 11 }}>
                          {log.timestamp ? dayjs(log.timestamp).format('YYYY-MM-DD HH:mm:ss') : ''}
                        </Text>
                      </div>
                    </div>
                  ),
                }))}
              />
            ) : (
              <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
                No activity recorded yet for this camera.
              </div>
            )}
          </div>
        ) : null}
      </Drawer>
    </div>
  );
}
