import React, { useState, useEffect, useCallback } from 'react';
import { Row, Col, Card, Statistic, Table, Tag, Typography, Spin } from 'antd';
import {
  TeamOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  PercentageOutlined,
} from '@ant-design/icons';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { apiGet } from '../api';
import dayjs from 'dayjs';

const { Title } = Typography;

const statusColors = { present: 'green', late: 'orange', absent: 'red' };
const methodColors = { manual: 'blue', rtsp_auto: 'purple' };

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [weeklyData, setWeeklyData] = useState([]);
  const [recentActivity, setRecentActivity] = useState([]);
  const [classStats, setClassStats] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchDashboard = useCallback(async () => {
    try {
      const [statsRes, weeklyRes, activityRes, classRes] = await Promise.all([
        apiGet('/dashboard/stats').catch(() => null),
        apiGet('/dashboard/weekly').catch(() => []),
        apiGet('/attendance/today').catch(() => []),
        apiGet('/dashboard/class-stats').catch(() => []),
      ]);
      if (statsRes) setStats(statsRes);
      if (Array.isArray(weeklyRes)) setWeeklyData(weeklyRes);
      if (Array.isArray(activityRes)) setRecentActivity(activityRes);
      else if (activityRes?.items) setRecentActivity(activityRes.items);
      if (Array.isArray(classRes)) setClassStats(classRes);
    } catch (err) {
      console.error('Dashboard fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboard();
    const interval = setInterval(fetchDashboard, 10000);
    return () => clearInterval(interval);
  }, [fetchDashboard]);

  const activityColumns = [
    {
      title: 'Student',
      dataIndex: 'student_name',
      key: 'student_name',
      render: (text, record) => text || record.student_code || `ID: ${record.student_id}`,
    },
    {
      title: 'Class',
      dataIndex: 'class_name',
      key: 'class_name',
      render: (text) => text || '-',
    },
    {
      title: 'Check In',
      dataIndex: 'check_in',
      key: 'check_in',
      render: (text) => text ? dayjs(text).format('HH:mm:ss') : '-',
    },
    {
      title: 'Method',
      dataIndex: 'method',
      key: 'method',
      render: (method) => (
        <Tag color={methodColors[method] || 'default'}>
          {method === 'rtsp_auto' ? 'Auto (Camera)' : 'Manual'}
        </Tag>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status) => (
        <Tag color={statusColors[status] || 'default'}>
          {status?.toUpperCase()}
        </Tag>
      ),
    },
  ];

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 100 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>Dashboard</Title>

      <Row gutter={[16, 16]} className="dashboard-stats" style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={4}>
          <Card>
            <Statistic
              title="Total Students"
              value={stats?.total_students ?? 0}
              prefix={<TeamOutlined />}
              valueStyle={{ color: '#1677ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={5}>
          <Card>
            <Statistic
              title="Present Today"
              value={stats?.present_today ?? 0}
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={5}>
          <Card>
            <Statistic
              title="Absent Today"
              value={stats?.absent_today ?? 0}
              prefix={<CloseCircleOutlined />}
              valueStyle={{ color: '#ff4d4f' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={5}>
          <Card>
            <Statistic
              title="Late Today"
              value={stats?.late_today ?? 0}
              prefix={<ClockCircleOutlined />}
              valueStyle={{ color: '#faad14' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={5}>
          <Card>
            <Statistic
              title="Attendance Rate"
              value={stats?.attendance_rate ?? 0}
              precision={1}
              suffix="%"
              prefix={<PercentageOutlined />}
              valueStyle={{ color: '#1677ff' }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} lg={16}>
          <Card title="Attendance Trend (Last 7 Days)">
            {weeklyData.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={weeklyData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={(val) => dayjs(val).format('MM/DD')}
                  />
                  <YAxis />
                  <Tooltip labelFormatter={(val) => dayjs(val).format('YYYY-MM-DD')} />
                  <Legend />
                  <Line type="monotone" dataKey="present" stroke="#52c41a" name="Present" strokeWidth={2} />
                  <Line type="monotone" dataKey="late" stroke="#faad14" name="Late" strokeWidth={2} />
                  <Line type="monotone" dataKey="absent" stroke="#ff4d4f" name="Absent" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ textAlign: 'center', padding: 60, color: '#999' }}>
                No attendance data available for the past 7 days.
              </div>
            )}
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="Class Breakdown" style={{ height: '100%' }}>
            {classStats.length > 0 ? (
              classStats.map((cls) => (
                <Card
                  key={cls.class_id}
                  size="small"
                  style={{ marginBottom: 8 }}
                  bodyStyle={{ padding: '8px 12px' }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <strong>{cls.class_name}</strong>
                    <Tag color={cls.attendance_rate >= 80 ? 'green' : cls.attendance_rate >= 50 ? 'orange' : 'red'}>
                      {cls.attendance_rate?.toFixed(0)}%
                    </Tag>
                  </div>
                  <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                    {cls.present_today}P / {cls.late_today}L / {cls.absent_today}A (of {cls.total_students})
                  </div>
                </Card>
              ))
            ) : (
              <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
                No class data available.
              </div>
            )}
          </Card>
        </Col>
      </Row>

      <Card title="Recent Attendance Activity">
        <Table
          columns={activityColumns}
          dataSource={recentActivity}
          rowKey="id"
          pagination={false}
          size="small"
        />
      </Card>
    </div>
  );
}
