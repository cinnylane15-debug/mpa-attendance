import React, { useState, useEffect } from 'react';
import {
  Table, Button, Select, Tag, DatePicker, Tabs, message, Space, Typography, Card,
} from 'antd';
import {
  DownloadOutlined, SearchOutlined, ReloadOutlined,
} from '@ant-design/icons';
import { apiGet, apiGetBlob } from '../api';
import { saveAs } from 'file-saver';
import dayjs from 'dayjs';

const { Title } = Typography;
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
      const data = await apiGet(`/attendance?${params.toString()}`);
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

  const columns = [
    {
      title: 'Student ID',
      dataIndex: 'student_code',
      key: 'student_code',
      width: 110,
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
      render: (text) => text || '-',
    },
    {
      title: 'Date',
      dataIndex: 'date',
      key: 'date',
      width: 110,
      render: (text) => dayjs(text).format('YYYY-MM-DD'),
    },
    {
      title: 'Check In',
      dataIndex: 'check_in',
      key: 'check_in',
      width: 100,
      render: (text) => text ? dayjs(text).format('HH:mm:ss') : '-',
    },
    {
      title: 'Check Out',
      dataIndex: 'check_out',
      key: 'check_out',
      width: 100,
      render: (text) => text ? dayjs(text).format('HH:mm:ss') : '-',
    },
    {
      title: 'Method',
      dataIndex: 'method',
      key: 'method',
      width: 120,
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
      width: 90,
      render: (status) => (
        <Tag color={statusColors[status] || 'default'}>
          {status?.toUpperCase()}
        </Tag>
      ),
    },
    {
      title: 'Confidence',
      dataIndex: 'confidence',
      key: 'confidence',
      width: 100,
      render: (val) => val != null ? `${(val * 100).toFixed(1)}%` : '-',
    },
  ];

  const tabItems = [
    {
      key: 'today',
      label: 'Today',
      children: (
        <>
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
            <Button icon={<ReloadOutlined />} onClick={fetchAttendance}>Refresh</Button>
          </div>
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
          <div className="filter-bar">
            <DatePicker
              value={selectedDate}
              onChange={(date) => setSelectedDate(date)}
              allowClear={false}
            />
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
            <Button icon={<SearchOutlined />} onClick={fetchAttendance}>Search</Button>
          </div>
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
    </div>
  );
}
