import React, { useState, useEffect } from 'react';
import {
  Table, Button, Modal, Form, Input, DatePicker, Calendar, message, Space, Typography,
  Popconfirm, Card, Row, Col, Tag, Badge, List,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, CalendarOutlined } from '@ant-design/icons';
import { apiGet, apiPost, apiPut, apiDelete } from '../api';
import dayjs from 'dayjs';
import isSameOrAfter from 'dayjs/plugin/isSameOrAfter';

dayjs.extend(isSameOrAfter);

const { Title, Text } = Typography;
const { TextArea } = Input;

export default function Holidays() {
  const [holidays, setHolidays] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingHoliday, setEditingHoliday] = useState(null);
  const [form] = Form.useForm();

  const fetchHolidays = async () => {
    setLoading(true);
    try {
      const data = await apiGet('/holidays');
      setHolidays(Array.isArray(data) ? data : data?.items || []);
    } catch (err) {
      message.error('Failed to load holidays');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHolidays();
  }, []);

  const openAddModal = () => {
    setEditingHoliday(null);
    form.resetFields();
    setModalOpen(true);
  };

  const openEditModal = (record) => {
    setEditingHoliday(record);
    form.setFieldsValue({
      name: record.name,
      date: dayjs(record.date),
      description: record.description || '',
    });
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const payload = {
        ...values,
        date: values.date.format('YYYY-MM-DD'),
      };
      if (editingHoliday) {
        await apiPut(`/holidays/${editingHoliday.id}`, payload);
        message.success('Holiday updated');
      } else {
        await apiPost('/holidays', payload);
        message.success('Holiday added');
      }
      setModalOpen(false);
      fetchHolidays();
    } catch (err) {
      if (err.message) message.error(err.message);
    }
  };

  const handleDelete = async (id) => {
    try {
      await apiDelete(`/holidays/${id}`);
      message.success('Holiday deleted');
      fetchHolidays();
    } catch (err) {
      message.error(err.message || 'Failed to delete holiday');
    }
  };

  const holidayDates = new Set(holidays.map((h) => h.date));

  const dateCellRender = (value) => {
    const dateStr = value.format('YYYY-MM-DD');
    const holiday = holidays.find((h) => h.date === dateStr);
    if (holiday) {
      return (
        <div>
          <Badge status="error" text={<Text style={{ fontSize: 11 }}>{holiday.name}</Text>} />
        </div>
      );
    }
    return null;
  };

  const upcomingHolidays = holidays
    .filter((h) => dayjs(h.date).isSameOrAfter(dayjs(), 'day'))
    .sort((a, b) => dayjs(a.date).diff(dayjs(b.date)));

  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      sorter: (a, b) => a.name.localeCompare(b.name),
    },
    {
      title: 'Date',
      dataIndex: 'date',
      key: 'date',
      sorter: (a, b) => dayjs(a.date).diff(dayjs(b.date)),
      render: (text) => dayjs(text).format('YYYY-MM-DD (dddd)'),
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      render: (text) => text || '-',
      ellipsis: true,
    },
    {
      title: 'Status',
      key: 'status',
      width: 100,
      render: (_, record) => {
        const isPast = dayjs(record.date).isBefore(dayjs(), 'day');
        return <Tag color={isPast ? 'default' : 'blue'}>{isPast ? 'Past' : 'Upcoming'}</Tag>;
      },
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 120,
      render: (_, record) => (
        <Space>
          <Button
            icon={<EditOutlined />}
            size="small"
            onClick={() => openEditModal(record)}
          />
          <Popconfirm
            title="Delete this holiday?"
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
        <Title level={4} style={{ margin: 0 }}>Holidays</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openAddModal}>
          Add Holiday
        </Button>
      </div>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} lg={16}>
          <Card title="Holiday Calendar" className="holiday-calendar">
            <Calendar
              fullscreen={false}
              cellRender={dateCellRender}
            />
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card
            title={
              <Space>
                <CalendarOutlined />
                <span>Upcoming Holidays</span>
              </Space>
            }
            style={{ height: '100%' }}
          >
            {upcomingHolidays.length > 0 ? (
              <List
                dataSource={upcomingHolidays.slice(0, 10)}
                renderItem={(item) => {
                  const daysUntil = dayjs(item.date).diff(dayjs(), 'day');
                  return (
                    <List.Item>
                      <List.Item.Meta
                        title={item.name}
                        description={
                          <div>
                            <div>{dayjs(item.date).format('MMMM D, YYYY (dddd)')}</div>
                            <Tag color="blue" style={{ marginTop: 4 }}>
                              {daysUntil === 0 ? 'Today' : daysUntil === 1 ? 'Tomorrow' : `In ${daysUntil} days`}
                            </Tag>
                          </div>
                        }
                      />
                    </List.Item>
                  );
                }}
              />
            ) : (
              <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
                No upcoming holidays
              </div>
            )}
          </Card>
        </Col>
      </Row>

      <Card title="All Holidays">
        <Table
          columns={columns}
          dataSource={holidays}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 20, showTotal: (total) => `Total: ${total} holidays` }}
        />
      </Card>

      <Modal
        title={editingHoliday ? 'Edit Holiday' : 'Add Holiday'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        okText={editingHoliday ? 'Update' : 'Add'}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="Holiday Name"
            rules={[{ required: true, message: 'Holiday name is required' }]}
          >
            <Input placeholder="e.g., Independence Day" />
          </Form.Item>
          <Form.Item
            name="date"
            label="Date"
            rules={[{ required: true, message: 'Date is required' }]}
          >
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <TextArea rows={3} placeholder="Optional description" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
