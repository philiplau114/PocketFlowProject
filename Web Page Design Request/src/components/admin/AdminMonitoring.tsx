import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../ui/table';
import { Alert, AlertDescription } from '../ui/alert';
import { Progress } from '../ui/progress';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';
import { toast } from 'sonner@2.0.3';
import { 
  Activity, 
  Clock, 
  RefreshCw, 
  AlertTriangle, 
  CheckCircle, 
  XCircle,
  Settings,
  Database,
  TrendingUp,
  Info
} from 'lucide-react';

// Mock data for admin monitoring
const mockThresholds = [
  { name: 'max_retry_attempts', value: 3 },
  { name: 'task_timeout_minutes', value: 30 },
  { name: 'queue_depth_warning', value: 50 },
  { name: 'wait_time_warning_minutes', value: 60 },
  { name: 'fine_tune_depth_limit', value: 5 }
];

const mockTaskStatus = [
  { status: 'new', count: 12 },
  { status: 'processing', count: 8 },
  { status: 'retrying', count: 5 },
  { status: 'completed', count: 247 },
  { status: 'failed', count: 3 }
];

const mockTaskAging = [
  { id: 1001, status: 'new', attempt_count: 1, created_at: '2024-03-10 10:30:00', updated_at: '2024-03-10 10:30:00', wait_mins: 45 },
  { id: 1002, status: 'retrying', attempt_count: 2, created_at: '2024-03-10 09:15:00', updated_at: '2024-03-10 10:45:00', wait_mins: 75 },
  { id: 1003, status: 'processing', attempt_count: 1, created_at: '2024-03-10 10:45:00', updated_at: '2024-03-10 10:50:00', wait_mins: 15 },
  { id: 1004, status: 'new', attempt_count: 1, created_at: '2024-03-10 08:30:00', updated_at: '2024-03-10 08:30:00', wait_mins: 120 }
];

const mockFineTuneChains = [
  { id: 2001, parent_task_id: 1500, fine_tune_depth: 2, attempt_count: 1, status: 'completed', updated_at: '2024-03-10 10:15:00' },
  { id: 2002, parent_task_id: 1501, fine_tune_depth: 3, attempt_count: 2, status: 'processing', updated_at: '2024-03-10 10:30:00' },
  { id: 2003, parent_task_id: 1502, fine_tune_depth: 1, attempt_count: 1, status: 'failed', updated_at: '2024-03-10 09:45:00' }
];

const mockDailyStats = [
  { date: '2024-03-04', completed: 45, failed: 2, retries: 8 },
  { date: '2024-03-05', completed: 52, failed: 1, retries: 6 },
  { date: '2024-03-06', completed: 48, failed: 3, retries: 12 },
  { date: '2024-03-07', completed: 61, failed: 1, retries: 4 },
  { date: '2024-03-08', completed: 58, failed: 2, retries: 9 },
  { date: '2024-03-09', completed: 55, failed: 0, retries: 5 },
  { date: '2024-03-10', completed: 38, failed: 1, retries: 7 }
];

const mockRecentActivity = [
  { id: 3001, status: 'completed', attempt_count: 1, fine_tune_depth: 0, weighted_score: 87.5, normalized_distance: 0.15, last_error: null, updated_at: '2024-03-10 11:00:00' },
  { id: 3002, status: 'failed', attempt_count: 3, fine_tune_depth: 2, weighted_score: null, normalized_distance: null, last_error: 'Connection timeout', updated_at: '2024-03-10 10:58:00' },
  { id: 3003, status: 'processing', attempt_count: 1, fine_tune_depth: 1, weighted_score: null, normalized_distance: null, last_error: null, updated_at: '2024-03-10 10:55:00' }
];

export function AdminMonitoring() {
  const [thresholds, setThresholds] = useState(mockThresholds);
  const [isUpdating, setIsUpdating] = useState(false);
  const queueDepth = 12;

  const handleThresholdChange = (name: string, value: string) => {
    setThresholds(prev => prev.map(threshold => 
      threshold.name === name ? { ...threshold, value: parseInt(value) || 0 } : threshold
    ));
  };

  const handleUpdateThresholds = async () => {
    setIsUpdating(true);
    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000));
      toast.success('Thresholds updated successfully');
    } catch (error) {
      toast.error('Failed to update thresholds');
    } finally {
      setIsUpdating(false);
    }
  };

  const getStatusBadge = (status: string) => {
    const variants = {
      new: 'secondary',
      processing: 'default',
      retrying: 'destructive',
      completed: 'default',
      failed: 'destructive'
    } as const;
    
    return <Badge variant={variants[status as keyof typeof variants] || 'default'}>{status}</Badge>;
  };

  const getStatusColor = (status: string) => {
    const colors = {
      new: '#6b7280',
      processing: '#3b82f6',
      retrying: '#f59e0b',
      completed: '#10b981',
      failed: '#ef4444'
    };
    return colors[status as keyof typeof colors] || '#6b7280';
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="flex items-center gap-2">
          ⚡ Controller/Worker Monitoring Dashboard
        </h1>
        <Button variant="outline" onClick={() => window.location.reload()}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Threshold Management */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            Current Thresholds (Editable)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Value</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {thresholds.map((threshold) => (
                  <TableRow key={threshold.name}>
                    <TableCell className="font-medium">{threshold.name}</TableCell>
                    <TableCell>
                      <Input
                        type="number"
                        value={threshold.value}
                        onChange={(e) => handleThresholdChange(threshold.name, e.target.value)}
                        className="w-24"
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <Button onClick={handleUpdateThresholds} disabled={isUpdating}>
              {isUpdating ? 'Updating...' : 'Update Thresholds'}
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {/* Task Status Overview */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart className="h-5 w-5" />
              Task Status Overview
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={mockTaskStatus}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="status" />
                  <YAxis />
                  <Tooltip />
                  <Bar 
                    dataKey="count" 
                    fill={(entry) => getStatusColor(entry.status)}
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Redis Queue Depth */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-5 w-5" />
              Redis Queue Depth
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-center space-y-4">
              <div className="text-4xl font-bold text-primary">{queueDepth}</div>
              <p className="text-sm text-muted-foreground">Tasks in queue</p>
              <Progress value={(queueDepth / 50) * 100} className="w-full" />
              {queueDepth > 30 && (
                <Alert>
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>Queue depth is high</AlertDescription>
                </Alert>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Task Aging / Wait Time */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Task Aging / Wait Time
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Attempts</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>Updated</TableHead>
                <TableHead>Wait (mins)</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {mockTaskAging.map((task) => (
                <TableRow 
                  key={task.id}
                  className={task.wait_mins > 60 ? 'bg-yellow-50 dark:bg-yellow-900/20' : ''}
                >
                  <TableCell className="font-medium">{task.id}</TableCell>
                  <TableCell>{getStatusBadge(task.status)}</TableCell>
                  <TableCell>{task.attempt_count}</TableCell>
                  <TableCell className="text-sm">{task.created_at}</TableCell>
                  <TableCell className="text-sm">{task.updated_at}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      {task.wait_mins > 60 && <AlertTriangle className="h-4 w-4 text-yellow-600" />}
                      {task.wait_mins}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Fine-Tune / Retry Chains */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <RefreshCw className="h-5 w-5" />
            Fine-Tune / Retry Chains
          </CardTitle>
        </CardHeader>
        <CardContent>
          {mockFineTuneChains.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead>Parent Task</TableHead>
                  <TableHead>Fine-Tune Depth</TableHead>
                  <TableHead>Attempts</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Updated</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {mockFineTuneChains.map((chain) => (
                  <TableRow key={chain.id}>
                    <TableCell className="font-medium">{chain.id}</TableCell>
                    <TableCell>{chain.parent_task_id}</TableCell>
                    <TableCell>{chain.fine_tune_depth}</TableCell>
                    <TableCell>{chain.attempt_count}</TableCell>
                    <TableCell>{getStatusBadge(chain.status)}</TableCell>
                    <TableCell className="text-sm">{chain.updated_at}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <Alert>
              <Info className="h-4 w-4" />
              <AlertDescription>No fine-tune chains currently active</AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Completions, Failures, Retries (Last 14 Days) */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            Daily Activity (Last 7 Days)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={mockDailyStats}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="completed" stroke="#10b981" strokeWidth={2} />
                <Line type="monotone" dataKey="failed" stroke="#ef4444" strokeWidth={2} />
                <Line type="monotone" dataKey="retries" stroke="#f59e0b" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Recent Task Activity */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Recent Task Activity
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Attempts</TableHead>
                <TableHead>Fine-Tune Depth</TableHead>
                <TableHead>Score</TableHead>
                <TableHead>Distance</TableHead>
                <TableHead>Last Error</TableHead>
                <TableHead>Updated</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {mockRecentActivity.map((activity) => (
                <TableRow key={activity.id}>
                  <TableCell className="font-medium">{activity.id}</TableCell>
                  <TableCell>{getStatusBadge(activity.status)}</TableCell>
                  <TableCell>{activity.attempt_count}</TableCell>
                  <TableCell>{activity.fine_tune_depth}</TableCell>
                  <TableCell>{activity.weighted_score || '-'}</TableCell>
                  <TableCell>{activity.normalized_distance || '-'}</TableCell>
                  <TableCell className="max-w-32 truncate">
                    {activity.last_error || '-'}
                  </TableCell>
                  <TableCell className="text-sm">{activity.updated_at}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <div className="text-center text-sm text-muted-foreground">
        Refresh the page to update live data. Last updated: {new Date().toLocaleString()}
      </div>
    </div>
  );
}