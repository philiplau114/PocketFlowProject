import React, { useState, createContext, useContext } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { LoginPage } from './components/auth/LoginPage';
import { StrategyDashboard } from './components/dashboard/StrategyDashboard';
import { PortfolioManagement } from './components/portfolio/PortfolioManagement';
import { AdminMonitoring } from './components/admin/AdminMonitoring';
import { AdminAuditLog } from './components/admin/AdminAuditLog';
import { SettingsPage } from './components/settings/SettingsPage';
import { NavigationLayout } from './components/layout/NavigationLayout';
import { Toaster } from './components/ui/sonner';

// Mock user types
type UserRole = 'admin' | 'trader' | 'viewer' | 'guest';

interface User {
  id: string;
  username: string;
  email: string;
  role: UserRole;
  openRouterApiKey?: string;
  registrationDate: string;
}

interface AuthContextType {
  user: User | null;
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
  register: (userData: any) => Promise<boolean>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

// Mock users for demo
const mockUsers: User[] = [
  {
    id: '1',
    username: 'admin',
    email: 'admin@trading.com',
    role: 'admin',
    openRouterApiKey: 'sk-or-v1-***',
    registrationDate: '2024-01-15'
  },
  {
    id: '2',
    username: 'trader1',
    email: 'trader@trading.com',
    role: 'trader',
    openRouterApiKey: 'sk-or-v1-***',
    registrationDate: '2024-02-01'
  },
  {
    id: '3',
    username: 'viewer1',
    email: 'viewer@trading.com',
    role: 'viewer',
    registrationDate: '2024-02-15'
  }
];

export default function App() {
  const [user, setUser] = useState<User | null>(null);

  const login = async (username: string, password: string): Promise<boolean> => {
    // Mock login - in real app would validate against backend
    const foundUser = mockUsers.find(u => u.username === username);
    if (foundUser && password === 'password') {
      setUser(foundUser);
      return true;
    }
    return false;
  };

  const logout = () => {
    setUser(null);
  };

  const register = async (userData: any): Promise<boolean> => {
    // Mock registration
    const newUser: User = {
      id: Date.now().toString(),
      username: userData.username,
      email: userData.email,
      role: 'viewer', // Default role
      openRouterApiKey: userData.openRouterApiKey,
      registrationDate: new Date().toISOString().split('T')[0]
    };
    mockUsers.push(newUser);
    setUser(newUser);
    return true;
  };

  const authValue: AuthContextType = {
    user,
    login,
    logout,
    register
  };

  return (
    <AuthContext.Provider value={authValue}>
      <Router>
        <div className="min-h-screen bg-background">
          <Routes>
            <Route 
              path="/login" 
              element={user ? <Navigate to="/dashboard" /> : <LoginPage />} 
            />
            <Route
              path="/*"
              element={
                user ? (
                  <NavigationLayout>
                    <Routes>
                      <Route path="/" element={<Navigate to="/dashboard" />} />
                      <Route path="/dashboard" element={<StrategyDashboard />} />
                      {user.role === 'trader' && (
                        <Route path="/portfolio" element={<PortfolioManagement />} />
                      )}
                      {user.role === 'admin' && (
                        <>
                          <Route path="/admin/monitoring" element={<AdminMonitoring />} />
                          <Route path="/admin/audit" element={<AdminAuditLog />} />
                        </>
                      )}
                      <Route path="/settings" element={<SettingsPage />} />
                    </Routes>
                  </NavigationLayout>
                ) : (
                  <Navigate to="/login" />
                )
              }
            />
          </Routes>
          <Toaster />
        </div>
      </Router>
    </AuthContext.Provider>
  );
}