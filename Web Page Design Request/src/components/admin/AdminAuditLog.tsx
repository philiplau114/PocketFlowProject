import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Badge } from '../ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Alert, AlertDescription } from '../ui/alert';
import { toast } from 'sonner@2.0.3';
import { 
  Shield, 
  Users, 
  CheckCircle, 
  XCircle, 
  Search,
  Filter,
  UserCheck,
  UserX,
  Info,
  Clock
} from 'lucide-react';

// Mock data for pending users
const mockPendingUsers = [
  {
    id: 1,
    username: 'newtrader1',
    email: 'newtrader1@email.com',
    registrationDate: '2024-03-10',
    requestedRole: 'trader'
  },
  {
    id: 2,
    username: 'analyst2',
    email: 'analyst2@email.com',
    registrationDate: '2024-03-09',
    requestedRole: 'viewer'
  },
  {
    id: 3,
    username: 'poweruser',
    email: 'poweruser@email.com',
    registrationDate: '2024-03-08',
    requestedRole: 'trader'
  }
];

// Mock audit log data
const mockAuditLog = [
  {
    id: 1,
    user: 'admin',
    action: 'user_approved',
    target: 'trader1',
    timestamp: '2024-03-10 10:30:00',
    details: 'Approved trader registration'
  },
  {
    id: 2,
    user: 'trader1',
    action: 'strategy_downloaded',
    target: 'Momentum Scalper Pro',
    timestamp: '2024-03-10 10:15:00',
    details: 'Downloaded .set file'
  },
  {
    id: 3,
    user: 'admin',
    action: 'threshold_updated',
    target: 'max_retry_attempts',
    timestamp: '2024-03-10 09:45:00',
    details: 'Changed from 2 to 3'
  },
  {
    id: 4,
    user: 'viewer1',
    action: 'strategy_viewed',
    target: 'Grid Master 2.0',
    timestamp: '2024-03-10 09:30:00',
    details: 'Viewed strategy details'
  },
  {
    id: 5,
    user: 'admin',
    action: 'user_denied',
    target: 'suspicioususer',
    timestamp: '2024-03-09 16:20:00',
    details: 'Registration denied - suspicious activity'
  },
  {
    id: 6,
    user: 'trader1',
    action: 'portfolio_created',
    target: 'Conservative Growth Portfolio',
    timestamp: '2024-03-09 14:10:00',
    details: 'Created new portfolio with 3 strategies'
  }
];

const actionTypes = ['all', 'user_approved', 'user_denied', 'strategy_downloaded', 'strategy_viewed', 'threshold_updated', 'portfolio_created'];

export function AdminAuditLog() {
  const [pendingUsers, setPendingUsers] = useState(mockPendingUsers);
  const [auditLog, setAuditLog] = useState(mockAuditLog);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedAction, setSelectedAction] = useState('all');
  const [dateFilter, setDateFilter] = useState('');

  const handleApproveUser = async (userId: number) => {
    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 500));
      
      const user = pendingUsers.find(u => u.id === userId);
      if (user) {
        // Remove from pending list
        setPendingUsers(prev => prev.filter(u => u.id !== userId));
        
        // Add to audit log
        const newLogEntry = {
          id: auditLog.length + 1,
          user: 'admin',
          action: 'user_approved',
          target: user.username,
          timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19),
          details: `Approved ${user.requestedRole} registration`
        };
        setAuditLog(prev => [newLogEntry, ...prev]);
        
        toast.success(`User ${user.username} approved successfully`);
      }
    } catch (error) {
      toast.error('Failed to approve user');
    }
  };

  const handleDenyUser = async (userId: number) => {
    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 500));
      
      const user = pendingUsers.find(u => u.id === userId);
      if (user) {
        // Remove from pending list
        setPendingUsers(prev => prev.filter(u => u.id !== userId));
        
        // Add to audit log
        const newLogEntry = {
          id: auditLog.length + 1,
          user: 'admin',
          action: 'user_denied',
          target: user.username,
          timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19),
          details: `Denied ${user.requestedRole} registration`
        };
        setAuditLog(prev => [newLogEntry, ...prev]);
        
        toast.success(`User ${user.username} denied`);
      }
    } catch (error) {
      toast.error('Failed to deny user');
    }
  };

  const filteredAuditLog = auditLog.filter(entry => {
    const matchesSearch = entry.user.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         entry.target.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         entry.details.toLowerCase().includes(searchTerm.toLowerCase());
    
    const matchesAction = selectedAction === 'all' || entry.action === selectedAction;
    
    const matchesDate = !dateFilter || entry.timestamp.startsWith(dateFilter);
    
    return matchesSearch && matchesAction && matchesDate;
  });

  const getActionBadge = (action: string) => {
    const variants = {
      user_approved: 'default',
      user_denied: 'destructive',
      strategy_downloaded: 'secondary',
      strategy_viewed: 'outline',
      threshold_updated: 'secondary',
      portfolio_created: 'default'
    } as const;
    
    return <Badge variant={variants[action as keyof typeof variants] || 'outline'}>{action}</Badge>;
  };

  const todayActions = auditLog.filter(entry => 
    entry.timestamp.startsWith(new Date().toISOString().split('T')[0])
  ).length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="flex items-center gap-2">
          👮 Admin Approval & Audit Log
        </h1>
      </div>

      {/* Summary Metrics */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2">
              <Users className="h-8 w-8 text-blue-600" />
              <div>
                <p className="text-sm font-medium text-muted-foreground">Pending Approvals</p>
                <p className="text-2xl font-bold">{pendingUsers.length}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2">
              <Clock className="h-8 w-8 text-green-600" />
              <div>
                <p className="text-sm font-medium text-muted-foreground">Actions Today</p>
                <p className="text-2xl font-bold">{todayActions}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2">
              <Shield className="h-8 w-8 text-purple-600" />
              <div>
                <p className="text-sm font-medium text-muted-foreground">Total Log Entries</p>
                <p className="text-2xl font-bold">{auditLog.length}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Pending User Approvals */}
      {pendingUsers.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <UserCheck className="h-5 w-5" />
              Pending User Approvals
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Username</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Registration Date</TableHead>
                  <TableHead>Requested Role</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pendingUsers.map((user) => (
                  <TableRow key={user.id}>
                    <TableCell className="font-medium">{user.username}</TableCell>
                    <TableCell>{user.email}</TableCell>
                    <TableCell>{user.registrationDate}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{user.requestedRole}</Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Button 
                          size="sm" 
                          onClick={() => handleApproveUser(user.id)}
                          className="bg-green-600 hover:bg-green-700"
                        >
                          <CheckCircle className="h-4 w-4 mr-1" />
                          Approve
                        </Button>
                        <Button 
                          size="sm" 
                          variant="destructive"
                          onClick={() => handleDenyUser(user.id)}
                        >
                          <XCircle className="h-4 w-4 mr-1" />
                          Deny
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {pendingUsers.length === 0 && (
        <Alert>
          <Info className="h-4 w-4" />
          <AlertDescription>No pending user approvals at this time.</AlertDescription>
        </Alert>
      )}

      {/* Audit Log */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Audit Log
          </CardTitle>
        </CardHeader>
        <CardContent>
          {/* Filters */}
          <div className="flex flex-col sm:flex-row gap-4 mb-6">
            <div className="flex items-center space-x-2 flex-1">
              <Search className="h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search users, targets, or details..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            
            <div className="flex items-center space-x-2">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <Select value={selectedAction} onValueChange={setSelectedAction}>
                <SelectTrigger className="w-48">
                  <SelectValue placeholder="Filter by action" />
                </SelectTrigger>
                <SelectContent>
                  {actionTypes.map((action) => (
                    <SelectItem key={action} value={action}>
                      {action === 'all' ? 'All Actions' : action.replace('_', ' ')}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            
            <div className="flex items-center space-x-2">
              <Label htmlFor="date-filter">Date:</Label>
              <Input
                id="date-filter"
                type="date"
                value={dateFilter}
                onChange={(e) => setDateFilter(e.target.value)}
                className="w-40"
              />
            </div>
          </div>

          {/* Audit Log Table */}
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>User</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Target</TableHead>
                <TableHead>Timestamp</TableHead>
                <TableHead>Details</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredAuditLog.length > 0 ? (
                filteredAuditLog.map((entry) => (
                  <TableRow key={entry.id}>
                    <TableCell className="font-medium">{entry.user}</TableCell>
                    <TableCell>{getActionBadge(entry.action)}</TableCell>
                    <TableCell>{entry.target}</TableCell>
                    <TableCell className="text-sm">{entry.timestamp}</TableCell>
                    <TableCell className="max-w-64 truncate">{entry.details}</TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-muted-foreground">
                    No audit log entries match your filters
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <div className="text-center text-sm text-muted-foreground">
        For admin assistance or questions, contact: admin@tradingbot.com
      </div>
    </div>
  );
}