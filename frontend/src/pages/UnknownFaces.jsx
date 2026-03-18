import React, { useState, useEffect } from 'react';
import {
  Card, Button, Select, Tag, message, Space, Typography, Image, Row, Col, Badge, Empty, Popconfirm, Modal,
} from 'antd';
import {
  UserAddOutlined, CloseOutlined, DeleteOutlined, ReloadOutlined, QuestionCircleOutlined,
} from '@ant-design/icons';
import { apiGet, apiPost, apiDelete } from '../api';

const { Title, Text } = Typography;
const { Option } = Select;

export default function UnknownFaces() {
  const [faces, setFaces] = useState([]);
  const [students, setStudents] = useState([]);
  const [stats, setStats] = useState({ total: 0, unresolved: 0 });
  const [loading, setLoading] = useState(false);
  const [showResolved, setShowResolved] = useState(false);
  const [assignModal, setAssignModal] = useState(null); // face id
  const [selectedStudent, setSelectedStudent] = useState(null);

  const fetchFaces = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (!showResolved) params.append('resolved', 'false');
      const data = await apiGet(`/unknown-faces?${params.toString()}`);
      setFaces(Array.isArray(data) ? data : []);
    } catch (err) {
      message.error('Failed to load unknown faces');
    } finally {
      setLoading(false);
    }
  };

  const fetchStudents = async () => {
    try {
      const data = await apiGet('/students');
      setStudents(Array.isArray(data) ? data : []);
    } catch { /* ignore */ }
  };

  const fetchStats = async () => {
    try {
      const data = await apiGet('/unknown-faces/stats');
      setStats(data);
    } catch { /* ignore */ }
  };

  useEffect(() => {
    fetchFaces();
    fetchStudents();
    fetchStats();
  }, [showResolved]);

  const handleAssign = async () => {
    if (!assignModal || !selectedStudent) return;
    try {
      await apiPost(`/unknown-faces/${assignModal}/assign`, { student_id: selectedStudent });
      message.success('Face assigned to student');
      setAssignModal(null);
      setSelectedStudent(null);
      fetchFaces();
      fetchStats();
    } catch (err) {
      message.error(err.message || 'Failed to assign face');
    }
  };

  const handleDismiss = async (id) => {
    try {
      await apiPost(`/unknown-faces/${id}/dismiss`, {});
      message.success('Face dismissed');
      fetchFaces();
      fetchStats();
    } catch (err) {
      message.error(err.message || 'Failed to dismiss face');
    }
  };

  const handleDelete = async (id) => {
    try {
      await apiDelete(`/unknown-faces/${id}`);
      message.success('Face deleted');
      fetchFaces();
      fetchStats();
    } catch (err) {
      message.error(err.message || 'Failed to delete face');
    }
  };

  return (
    <div>
      <div className="page-header">
        <Space>
          <Title level={4} style={{ margin: 0 }}>Unknown Faces</Title>
          <Badge count={stats.unresolved} showZero style={{ backgroundColor: stats.unresolved > 0 ? '#f5222d' : '#d9d9d9' }} />
        </Space>
        <Space>
          <Button
            size="small"
            onClick={() => setShowResolved(!showResolved)}
          >
            {showResolved ? 'Hide Resolved' : 'Show All'}
          </Button>
          <Button icon={<ReloadOutlined />} onClick={() => { fetchFaces(); fetchStats(); }}>
            Refresh
          </Button>
        </Space>
      </div>

      {faces.length === 0 && !loading ? (
        <Card>
          <Empty
            image={<QuestionCircleOutlined style={{ fontSize: 48, color: '#ccc' }} />}
            description="No unknown faces to review"
          />
        </Card>
      ) : (
        <Row gutter={[12, 12]}>
          {faces.map((face) => (
            <Col xs={12} sm={8} md={6} lg={4} key={face.id}>
              <Card
                size="small"
                cover={
                  <Image
                    src={`/uploads/unknown_faces/${face.face_image_path}`}
                    alt="Unknown face"
                    style={{ objectFit: 'cover', height: 160 }}
                    fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mN8/+F9PQAI8wNPvd7POQAAAABJRU5ErkJggg=="
                  />
                }
                actions={[
                  <Button
                    type="link"
                    size="small"
                    icon={<UserAddOutlined />}
                    onClick={() => { setAssignModal(face.id); setSelectedStudent(face.best_match_student_id); }}
                    disabled={face.is_resolved}
                  >
                    Assign
                  </Button>,
                  <Popconfirm title="Dismiss this face?" onConfirm={() => handleDismiss(face.id)}>
                    <Button type="link" size="small" icon={<CloseOutlined />} disabled={face.is_resolved}>
                      Dismiss
                    </Button>
                  </Popconfirm>,
                  <Popconfirm title="Delete permanently?" onConfirm={() => handleDelete(face.id)}>
                    <Button type="link" size="small" icon={<DeleteOutlined />} danger />
                  </Popconfirm>,
                ]}
              >
                <div style={{ fontSize: 11 }}>
                  {face.confidence != null && (
                    <div>
                      <Text type="secondary">Match: </Text>
                      <Tag color={face.confidence > 0.5 ? 'orange' : 'red'} style={{ fontSize: 11 }}>
                        {(face.confidence * 100).toFixed(0)}%
                      </Tag>
                    </div>
                  )}
                  {face.best_match_name && (
                    <div>
                      <Text type="secondary">Best: </Text>
                      <Text>{face.best_match_name}</Text>
                    </div>
                  )}
                  <div>
                    <Text type="secondary">{face.camera_name || 'Unknown camera'}</Text>
                  </div>
                  {face.is_resolved && (
                    <Tag color="green" style={{ marginTop: 4 }}>
                      {face.assigned_student_name ? `Assigned: ${face.assigned_student_name}` : 'Dismissed'}
                    </Tag>
                  )}
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      <Modal
        title="Assign Face to Student"
        open={!!assignModal}
        onOk={handleAssign}
        onCancel={() => { setAssignModal(null); setSelectedStudent(null); }}
        okText="Assign"
        okButtonProps={{ disabled: !selectedStudent }}
      >
        <div style={{ marginBottom: 16 }}>
          <Text>Select the student this face belongs to:</Text>
        </div>
        <Select
          showSearch
          placeholder="Search for a student..."
          style={{ width: '100%' }}
          value={selectedStudent}
          onChange={setSelectedStudent}
          optionFilterProp="children"
          filterOption={(input, option) =>
            option.children.toLowerCase().includes(input.toLowerCase())
          }
        >
          {students.map((s) => (
            <Option key={s.id} value={s.id}>
              {s.name} ({s.student_id}){s.class_name ? ` - ${s.class_name}` : ''}
            </Option>
          ))}
        </Select>
      </Modal>
    </div>
  );
}
