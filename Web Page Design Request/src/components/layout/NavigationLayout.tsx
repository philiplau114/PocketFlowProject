import React from 'react';
import { Sidebar, SidebarContent, SidebarFooter, SidebarHeader, SidebarMenu, SidebarMenuButton, SidebarMenuItem, SidebarProvider, SidebarTrigger } from '../ui/sidebar';
import { Button } from '../ui/button';
import { useAuth } from '../../App';
import { useNavigate, useLocation } from 'react-router-dom';
import { 
  TrendingUp, 
  BarChart3, 
  Settings, 
  LogOut, 
  Shield, 
  FileText,
  Briefcase,
  Activity
} from 'lucide-react';

interface NavigationLayoutProps {
  children: React.ReactNode;
}

export function NavigationLayout({ children }: NavigationLayoutProps) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const navigationItems = [
    {
      icon: BarChart3,
      label: 'Strategy Dashboard',
      path: '/dashboard',
      roles: ['admin', 'trader', 'viewer', 'guest']
    },
    {
      icon: Briefcase,
      label: 'Portfolio Management',
      path: '/portfolio',
      roles: ['trader']
    },
    {
      icon: Activity,
      label: 'System Monitoring',
      path: '/admin/monitoring',
      roles: ['admin']
    },
    {
      icon: Shield,
      label: 'Admin Audit Log',
      path: '/admin/audit',
      roles: ['admin']
    },
    {
      icon: Settings,
      label: 'Settings',
      path: '/settings',
      roles: ['admin', 'trader', 'viewer']
    }
  ];

  const filteredItems = navigationItems.filter(item => 
    user && item.roles.includes(user.role)
  );

  return (
    <SidebarProvider>
      <div className="flex min-h-screen w-full">
        <Sidebar>
          <SidebarHeader className="p-4">
            <div className="flex items-center space-x-2">
              <TrendingUp className="h-6 w-6 text-primary" />
              <span className="font-bold text-lg">TradingBot Pro</span>
            </div>
          </SidebarHeader>
          
          <SidebarContent>
            <SidebarMenu>
              {filteredItems.map((item) => (
                <SidebarMenuItem key={item.path}>
                  <SidebarMenuButton
                    isActive={location.pathname === item.path}
                    onClick={() => navigate(item.path)}
                  >
                    <item.icon className="h-4 w-4" />
                    <span>{item.label}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarContent>
          
          <SidebarFooter className="p-4">
            <div className="space-y-2">
              <div className="text-sm text-muted-foreground">
                Logged in as: <span className="font-medium">{user?.username}</span>
              </div>
              <div className="text-xs text-muted-foreground">
                Role: {user?.role}
              </div>
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={handleLogout}
                className="w-full justify-start"
              >
                <LogOut className="h-4 w-4 mr-2" />
                Logout
              </Button>
            </div>
          </SidebarFooter>
        </Sidebar>
        
        <main className="flex-1">
          <div className="flex items-center gap-2 p-4 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <SidebarTrigger />
            <div className="font-medium">
              {filteredItems.find(item => item.path === location.pathname)?.label || 'Dashboard'}
            </div>
          </div>
          <div className="p-6">
            {children}
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
}