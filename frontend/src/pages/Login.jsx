import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Form, Input, Button, Card, message, Typography } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { login, fetchCurrentUser } from '../api';
import { useAuth } from '../context/AuthContext';

const { Title, Text } = Typography;

export default function Login() {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { loginUser } = useAuth();

  const from = location.state?.from?.pathname || '/';

  const handleSubmit = async (values) => {
    setLoading(true);
    try {
      const data = await login(values.username, values.password);
      const token = data.access_token;
      localStorage.setItem('token', token);
      const userData = await fetchCurrentUser();
      loginUser(token, userData);
      message.success('Login successful');
      navigate(from, { replace: true });
    } catch (err) {
      message.error(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <Card className="login-card" bordered={false}>
        <div className="login-logo">
          <div style={{ fontSize: 48 }}>🏫</div>
          <Title level={3} style={{ marginTop: 8, marginBottom: 4 }}>MPA Attendance</Title>
          <Text type="secondary">School Attendance Management System</Text>
        </div>
        <Form
          name="login"
          onFinish={handleSubmit}
          size="large"
          autoComplete="off"
        >
          <Form.Item
            name="username"
            rules={[{ required: true, message: 'Please enter your username' }]}
          >
            <Input
              prefix={<UserOutlined />}
              placeholder="Username"
            />
          </Form.Item>
          <Form.Item
            name="password"
            rules={[{ required: true, message: 'Please enter your password' }]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="Password"
            />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block>
              Sign In
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
