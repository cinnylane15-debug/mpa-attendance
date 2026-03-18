import React, { useState, useEffect } from 'react';
import {
  Table, Button, Select, Tag, DatePicker, Tabs, message, Space, Typography, Card,
  Modal, Image, List, Tooltip,
} from 'antd';
import {
  DownloadOutlined, SearchOutlined, ReloadOutlined, CameraOutlined, EyeOutlined,
} from '@ant-design/icons';
import { apiGet, apiGetBlob } from '../api';
import { saveAs } from 'file-saver';
import dayjs from 'dayjs';

const { Title, Text } = Typography;
const { Option } = Select;
const { RangePicker } = DatePicker;

const statusColors = { present: 'green', late: 'orange', absent: 'red' };
const methodColors = { manual: 'blue', rtsp_auto: 'purple' };

export default function Attendance() {
  const [records, setRecords] = useState([]);
  const [classes, setClasses] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedDate, setSelectedDate] = useState(dayjs());
  const [filterClass, setFilterClass] = useState(null);
  const [activeTab, setActiveTab] = useState('today');
  const [exportRange, setExportRange] = useState(null);
  const [exportClassId, setExportClassId] = useState(null);
  const [exporting, setExporting] = useState(false);

  // Detection logs modal
  const [logsModalOpen, setLogsModalOpen] = useState(false);
  const [logsLoading, setLogsLoading] = useState(false);
  const [detectionLogs, setDetectionLogs] = useState([]);
  const [logsTitle, setLogsTitle] = useState('');

  const fetchClasses = async () => {
    try {
      const data = await apiGet('/classes');
      setClasses(Array.isArray(data) ? data : data?.items || []);
    } catch {
      // ignore
    }
  };

  const fetchAttendance = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (activeTab === 'today') {
        params.append('date', dayjs().format('YYYY-MM-DD'));
      } else if (selectedDate) {
        params.append('date', selectedDate.format('YYYY-MM-DD'));
      }
      if (filterClass) params.append('class_id', filterClass);
      const endpoint = activeTab === 'today' ? '/attendance/today' : '/attendance/records';
      const data = await apiGet(`${endpoint}?${params.toString()}`);
      setRecords(Array.isArray(data) ? data : data?.items || []);
    } catch (err) {
      message.error('Failed to load attendance records');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchClasses();
  }, []);

  useEffect(() => {
    fetchAttendance();
  }, [activeTab, selectedDate, filterClass]);

  const handleExport = async () => {
    if (!exportRange || exportRange.length !== 2) {
      message.warning('Please select a date range for export');
      return;
    }
    setExporting(true);
    try {
      const params = new URLSearchParams();
      params.append('start_date', exportRange[0].format('YYYY-MM-DD'));
      params.append('end_date', exportRange[1].format('YYYY-MM-DD'));
      if (exportClassId) params.append('class_id', exportClassId);
      const blob = await apiGetBlob(`/attendance/export?${params.toString()}`);
      const filename = `attendance_${exportRange[0].format('YYYYMMDD')}_${exportRange[1].format('YYYYMMDD')}.xlsx`;
      saveAs(blob, filename);
      message.success('Export downloaded');
    } catch (err) {
      message.error(err.message || 'Export failed');
    } finally {
      setExporting(false);
    }
  };

  const openDetectionLogs = async (record) => {
    setLogsTitle(`${record.student_name || 'Student'} — ${dayjs(record.date).format('YYYY-MM-DD')}`);
    setLogsModalOpen(true);
    setLogsLoading(true);
    try {
      const data = await apiGet(`/attendance/detection-logs/${record.id}`);
      setDetectionLogs(Array.isArray(data) ? data : []);
    } catch {
      message.error('Failed to load detection logs');
      setDetectionLogs([]);
    } finally {
      setLogsLoading(false);
    }
  };

  const photoImg = (path, size = 48) => {
    if (!path) return '-';
    // Handle both full paths and relative
    const src = path.startsWith('/') ? `/uploads/${path.split('/uploads/')[1] || path.split('/app/uploads/')[1] || ''}` : `/uploads/${path}`;
    return (
      <Image
        src={src}
        width={size}
        height={size}
        style={{ objectFit: 'cover', borderRadius: 4 }}
        preview={{ mask: <EyeOutlined /> }}
        fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPj/HwADBwIAMCbHYQAAAABJRU5ErkJggg=="
      />
    );
  };

  const columns = [
    {
      title: 'Student ID',
      dataIndex: 'student_code',
      key: 'student_code',
      width: 100,
      render: (text) => text || '-',
    },
    {
      title: 'Name',
      dataIndex: 'student_name',
      key: 'student_name',
      render: (text, record) => text || `Student #${record.student_id}`,
    },
    {
      title: 'Class',
      dataIndex: 'class_name',
      key: 'class_name',
      width: 100,
      render: (text) => text || '-',
    },
    {
      title: 'Check In',
      key: 'check_in_group',
      width: 160,
      render: (_, record) => (
        <Space size={8}>
          {photoImg(record.check_in_photo, 40)}
          <div>
            <div>{record.check_in ? dayjs(record.check_in).format('HH:mm:ss') : '-'}</div>
            {record.confidence != null && (
              <Text type="secondary" style={{ fontSize: 11 }}>{(record.confidence * 100).toFixed(0)}%</Text>
            )}
          </div>
        </Space>
      ),
    },
    {
      title: 'Check Out',
      key: 'check_out_group',
      width: 160,
      render: (_, record) => (
        <Space size={8}>
          {photoImg(record.check_out_photo, 40)}
          <div>
            <div>{record.check_out ? dayjs(record.check_out).format('HH:mm:ss') : '-'}</div>
            {record.check_out_confidence != null && (
              <Text type="secondary" style={{ fontSize: 11 }}>{(record.check_out_confidence * 100).toFixed(0)}%</Text>
            )}
          </div>
        </Space>
      ),
    },
    {
      title: 'Method',
      dataIndex: 'method',
      key: 'method',
      width: 110,
      render: (method) => (
        <Tag color={methodColors[method] || 'default'}>
          {method === 'rtsp_auto' ? 'Auto' : 'Manual'}
        </Tag>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (status) => (
        <Tag color={statusColors[status] || 'default'}>
          {status?.toUpperCase()}
        </Tag>
      ),
    },
    {
      title: 'Logs',
      key: 'logs',
      width: 70,
      render: (_, record) => (
        <Tooltip title="View all detection photos">
          <Button
            type="link"
            icon={<CameraOutlined />}
            onClick={() => openDetectionLogs(record)}
            size="small"
          />
        </Tooltip>
      ),
    },
  ];

  const filterBar = (extra) => (
    <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap', alignItems: 'center' }}>
      {extra}
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
      <Button icon={<ReloadOutlined />} onClick={fetchAttendance}>Refresh</Button>
    </div>
  );

  const tabItems = [
    {
      key: 'today',
      label: 'Today',
      children: (
        <>
          {filterBar()}
          <Table
            columns={columns}
            dataSource={records}
            rowKey="id"
            loading={loading}
            pagination={{ pageSize: 50, showSizeChanger: true, showTotal: (t) => `Total: ${t} records` }}
            size="small"
          />
        </>
      ),
    },
    {
      key: 'history',
      label: 'History',
      children: (
        <>
          {filterBar(
            <DatePicker
              value={selectedDate}
              onChange={(date) => setSelectedDate(date)}
              allowClear={false}
            />
          )}
          <Table
            columns={columns}
            dataSource={records}
            rowKey="id"
            loading={loading}
            pagination={{ pageSize: 50, showSizeChanger: true, showTotal: (t) => `Total: ${t} records` }}
            size="small"
          />
        </>
      ),
    },
  ];

  return (
    <div>
      <div className="page-header">
        <Title level={4} style={{ margin: 0 }}>Attendance Records</Title>
      </div>

      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <span style={{ fontWeight: 500 }}>Export to Excel:</span>
          <RangePicker
            value={exportRange}
            onChange={(dates) => setExportRange(dates)}
          />
          <Select
            placeholder="Class (optional)"
            allowClear
            style={{ width: 180 }}
            value={exportClassId}
            onChange={(val) => setExportClassId(val)}
          >
            {classes.map((cls) => (
              <Option key={cls.id} value={cls.id}>{cls.name}</Option>
            ))}
          </Select>
          <Button
            type="primary"
            icon={<DownloadOutlined />}
            onClick={handleExport}
            loading={exporting}
          >
            Export
          </Button>
        </Space>
      </Card>

      <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />

      {/* Detection Logs Modal */}
      <Modal
        title={`Detection Logs: ${logsTitle}`}
        open={logsModalOpen}
        onCancel={() => setLogsModalOpen(false)}
        footer={null}
        width={700}
      >
        {logsLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}>Loading...</div>
        ) : detectionLogs.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>No detection logs found</div>
        ) : (
          <List
            dataSource={detectionLogs}
            renderItem={(log) => {
              const src = log.photo_path?.startsWith('/')
                ? `/uploads/${log.photo_path.split('/uploads/')[1] || log.photo_path.split('/app/uploads/')[1] || ''}`
                : `/uploads/${log.photo_path}`;
              return (
                <List.Item>
                  <Space size={16} align="start">
                    <Image
                      src={src}
                      width={120}
                      height={120}
                      style={{ objectFit: 'cover', borderRadius: 6 }}
                      preview
                      fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPj/HwADBwIAMCbHYQAAAABJRU5ErkJggg=="
                    />
                    <div>
                      <div style={{ fontWeight: 600, fontSize: 15 }}>
                        {log.detected_at ? dayjs(log.detected_at).format('HH:mm:ss') : '-'}
                      </div>
                      <div style={{ color: '#666', marginTop: 4 }}>
                        {log.detected_at ? dayjs(log.detected_at).format('YYYY-MM-DD') : ''}
                      </div>
                      <div style={{ marginTop: 4 }}>
                        <Tag color="blue">{log.camera_name || 'Unknown'}</Tag>
                        {log.confidence != null && (
                          <Tag color={log.confidence >= 0.5 ? 'green' : 'orange'}>
                            {(log.confidence * 100).toFixed(1)}%
                          </Tag>
                        )}
                      </div>
                    </div>
                  </Space>
                </List.Item>
              );
            }}
          />
        )}
      </Modal>
    </div>
  );
}
