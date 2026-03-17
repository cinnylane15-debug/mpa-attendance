import React, { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Dropdown, Avatar, Typography, theme } from 'antd';
import {
  DashboardOutlined,
  TeamOutlined,
  BookOutlined,
  CheckCircleOutlined,
  CameraOutlined,
  ScheduleOutlined,
  CalendarOutlined,
  UserOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons';
import { useAuth } from '../context/AuthContext';

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: 'Dashboard' },
  { key: '/students', icon: <TeamOutlined />, label: 'Students' },
  { key: '/classes', icon: <BookOutlined />, label: 'Classes' },
  { key: '/attendance', icon: <CheckCircleOutlined />, label: 'Attendance' },
  { key: '/cameras', icon: <CameraOutlined />, label: 'Cameras' },
  { key: '/schedules', icon: <ScheduleOutlined />, label: 'Schedules' },
  { key: '/holidays', icon: <CalendarOutlined />, label: 'Holidays' },
];

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const { token: themeToken } = theme.useToken();

  const handleMenuClick = ({ key }) => {
    navigate(key);
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const userMenuItems = [
    {
      key: 'user-info',
      label: (
        <div>
          <div style={{ fontWeight: 600 }}>{user?.username || 'User'}</div>
          <div style={{ fontSize: 12, color: '#888' }}>{user?.role || 'teacher'}</div>
        </div>
      ),
      disabled: true,
    },
    { type: 'divider' },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: 'Logout',
      onClick: handleLogout,
    },
  ];

  const selectedKey = menuItems.find(
    (item) => item.key !== '/' && location.pathname.startsWith(item.key)
  )?.key || '/';

  return (
    <Layout className="site-layout">
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        style={{
          overflow: 'auto',
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          zIndex: 10,
        }}
      >
        <div className={`logo ${collapsed ? 'logo-collapsed' : ''}`}>
          {collapsed ? 'MPA' : 'MPA Attendance'}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={handleMenuClick}
        />
      </Sider>
      <Layout style={{ marginLeft: collapsed ? 80 : 200, transition: 'margin-left 0.2s' }}>
        <Header
          style={{
            background: '#fff',
            boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
            position: 'sticky',
            top: 0,
            zIndex: 9,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center' }}>
            {React.createElement(collapsed ? MenuUnfoldOutlined : MenuFoldOutlined, {
              style: { fontSize: 18, cursor: 'pointer' },
              onClick: () => setCollapsed(!collapsed),
            })}
            <Text strong style={{ marginLeft: 16, fontSize: 16 }}>
              School Attendance Management System
            </Text>
          </div>
          <div className="header-right">
            <Dropdown menu={{ items: userMenuItems }} placement="bottomRight" trigger={['click']}>
              <div style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
                <Avatar icon={<UserOutlined />} style={{ backgroundColor: themeToken.colorPrimary }} />
                <Text>{user?.username}</Text>
              </div>
            </Dropdown>
          </div>
        </Header>
        <Content>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
