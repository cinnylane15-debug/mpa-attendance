import React, { useState, useEffect } from 'react';
import {
  Table, Button, Modal, Form, Select, TimePicker, Switch, message, Space, Typography, Popconfirm, Card, Empty,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { apiGet, apiPost, apiPut, apiDelete } from '../api';
import dayjs from 'dayjs';

const { Title } = Typography;
const { Option } = Select;

const DAYS_OF_WEEK = [
  { value: 0, label: 'Monday' },
  { value: 1, label: 'Tuesday' },
  { value: 2, label: 'Wednesday' },
  { value: 3, label: 'Thursday' },
  { value: 4, label: 'Friday' },
  { value: 5, label: 'Saturday' },
  { value: 6, label: 'Sunday' },
];

function dayName(dayNum) {
  return DAYS_OF_WEEK.find((d) => d.value === dayNum)?.label || `Day ${dayNum}`;
}

export default function Schedules() {
  const [classes, setClasses] = useState([]);
  const [schedules, setSchedules] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedClassId, setSelectedClassId] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState(null);
  const [form] = Form.useForm();

  const fetchClasses = async () => {
    try {
      const data = await apiGet('/classes');
      setClasses(Array.isArray(data) ? data : data?.items || []);
    } catch {
      // ignore
    }
  };

  const fetchSchedules = async () => {
    if (!selectedClassId) {
      setSchedules([]);
      return;
    }
    setLoading(true);
    try {
      const data = await apiGet(`/schedules?class_id=${selectedClassId}`);
      setSchedules(Array.isArray(data) ? data : data?.items || []);
    } catch (err) {
      message.error('Failed to load schedules');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchClasses();
  }, []);

  useEffect(() => {
    fetchSchedules();
  }, [selectedClassId]);

  const openAddModal = () => {
    if (!selectedClassId) {
      message.warning('Please select a class first');
      return;
    }
    setEditingSchedule(null);
    form.resetFields();
    form.setFieldsValue({ is_active: true });
    setModalOpen(true);
  };

  const openEditModal = (record) => {
    setEditingSchedule(record);
    form.setFieldsValue({
      day_of_week: record.day_of_week,
      start_time: record.start_time ? dayjs(record.start_time, 'HH:mm:ss') : null,
      end_time: record.end_time ? dayjs(record.end_time, 'HH:mm:ss') : null,
      is_active: record.is_active,
    });
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const payload = {
        ...values,
        start_time: values.start_time.format('HH:mm:ss'),
        end_time: values.end_time.format('HH:mm:ss'),
        class_id: selectedClassId,
      };
      if (editingSchedule) {
        const { class_id: _cid, ...updateData } = payload;
        await apiPut(`/schedules/${editingSchedule.id}`, updateData);
        message.success('Schedule updated');
      } else {
        await apiPost('/schedules', payload);
        message.success('Schedule added');
      }
      setModalOpen(false);
      fetchSchedules();
    } catch (err) {
      if (err.message) message.error(err.message);
    }
  };

  const handleDelete = async (id) => {
    try {
      await apiDelete(`/schedules/${id}`);
      message.success('Schedule deleted');
      fetchSchedules();
    } catch (err) {
      message.error(err.message || 'Failed to delete schedule');
    }
  };

  const columns = [
    {
      title: 'Day',
      dataIndex: 'day_of_week',
      key: 'day_of_week',
      sorter: (a, b) => a.day_of_week - b.day_of_week,
      render: (val) => dayName(val),
    },
    {
      title: 'Start Time',
      dataIndex: 'start_time',
      key: 'start_time',
      render: (val) => {
        if (!val) return '-';
        const t = dayjs(val, 'HH:mm:ss');
        return t.isValid() ? t.format('hh:mm A') : val;
      },
    },
    {
      title: 'End Time',
      dataIndex: 'end_time',
      key: 'end_time',
      render: (val) => {
        if (!val) return '-';
        const t = dayjs(val, 'HH:mm:ss');
        return t.isValid() ? t.format('hh:mm A') : val;
      },
    },
    {
      title: 'Active',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (active) => (
        <Switch checked={active} disabled size="small" />
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 140,
      render: (_, record) => (
        <Space>
          <Button
            icon={<EditOutlined />}
            size="small"
            onClick={() => openEditModal(record)}
          />
          <Popconfirm
            title="Delete this schedule?"
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
        <Title level={4} style={{ margin: 0 }}>Class Schedules</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openAddModal}>
          Add Schedule
        </Button>
      </div>

      <div className="filter-bar">
        <Select
          placeholder="Select a class to view schedule"
          style={{ width: 300 }}
          value={selectedClassId}
          onChange={(val) => setSelectedClassId(val)}
          showSearch
          optionFilterProp="children"
        >
          {classes.map((cls) => (
            <Option key={cls.id} value={cls.id}>{cls.name}{cls.section ? ` - ${cls.section}` : ''}</Option>
          ))}
        </Select>
      </div>

      {selectedClassId ? (
        <Table
          columns={columns}
          dataSource={schedules}
          rowKey="id"
          loading={loading}
          pagination={false}
          locale={{ emptyText: 'No schedules defined for this class. Click "Add Schedule" to create one.' }}
        />
      ) : (
        <Card>
          <Empty description="Select a class to view and manage its schedule" />
        </Card>
      )}

      <Modal
        title={editingSchedule ? 'Edit Schedule' : 'Add Schedule'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        okText={editingSchedule ? 'Update' : 'Add'}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="day_of_week"
            label="Day of Week"
            rules={[{ required: true, message: 'Please select a day' }]}
          >
            <Select placeholder="Select day">
              {DAYS_OF_WEEK.map((day) => (
                <Option key={day.value} value={day.value}>{day.label}</Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item
            name="start_time"
            label="Start Time"
            rules={[{ required: true, message: 'Start time is required' }]}
          >
            <TimePicker format="HH:mm" style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item
            name="end_time"
            label="End Time"
            rules={[{ required: true, message: 'End time is required' }]}
          >
            <TimePicker format="HH:mm" style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item
            name="is_active"
            label="Active"
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
