import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Input } from '../ui/input';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../ui/table';
import { Separator } from '../ui/separator';
import { Alert, AlertDescription } from '../ui/alert';
import { useAuth } from '../../App';
import { 
  Search, 
  Download, 
  TrendingUp, 
  TrendingDown, 
  CheckCircle, 
  XCircle,
  BarChart3,
  Target,
  DollarSign,
  Percent,
  Info
} from 'lucide-react';

// Mock strategy data
const mockStrategies = [
  {
    id: 1,
    rank: 1,
    name: 'Momentum Scalper Pro',
    symbol: 'EURUSD',
    netProfit: 25420.50,
    maxDD: -1250.30,
    totalTrades: 1247,
    recoveryFactor: 20.33,
    score: 92.5,
    winRate: 68.5,
    profitFactor: 1.85,
    expectedPayoff: 20.40,
    distance: 0.12,
    status: 'active',
    createdDate: '2024-01-15',
    hasSetFile: true,
    hasEquityCurve: true,
    criteriaStatus: [
      { name: 'Min Trades', passed: true, reason: '1247 trades > 100 minimum' },
      { name: 'Max Drawdown', passed: true, reason: '4.9% < 15% limit' },
      { name: 'Profit Factor', passed: true, reason: '1.85 > 1.3 minimum' },
      { name: 'Win Rate', passed: true, reason: '68.5% > 50% minimum' }
    ]
  },
  {
    id: 2,
    rank: 2,
    name: 'Grid Master 2.0',
    symbol: 'GBPUSD',
    netProfit: 18750.25,
    maxDD: -2100.75,
    totalTrades: 892,
    recoveryFactor: 8.93,
    score: 87.2,
    winRate: 72.1,
    profitFactor: 1.67,
    expectedPayoff: 21.03,
    distance: 0.18,
    status: 'active',
    createdDate: '2024-01-22',
    hasSetFile: true,
    hasEquityCurve: false,
    criteriaStatus: [
      { name: 'Min Trades', passed: true, reason: '892 trades > 100 minimum' },
      { name: 'Max Drawdown', passed: true, reason: '11.2% < 15% limit' },
      { name: 'Profit Factor', passed: true, reason: '1.67 > 1.3 minimum' },
      { name: 'Win Rate', passed: true, reason: '72.1% > 50% minimum' }
    ]
  },
  {
    id: 3,
    rank: 3,
    name: 'Trend Follower Elite',
    symbol: 'USDJPY',
    netProfit: 15200.80,
    maxDD: -3250.45,
    totalTrades: 456,
    recoveryFactor: 4.68,
    score: 79.8,
    winRate: 58.3,
    profitFactor: 1.42,
    expectedPayoff: 33.33,
    distance: 0.25,
    status: 'paused',
    createdDate: '2024-02-01',
    hasSetFile: false,
    hasEquityCurve: true,
    criteriaStatus: [
      { name: 'Min Trades', passed: true, reason: '456 trades > 100 minimum' },
      { name: 'Max Drawdown', passed: false, reason: '21.4% > 15% limit' },
      { name: 'Profit Factor', passed: true, reason: '1.42 > 1.3 minimum' },
      { name: 'Win Rate', passed: true, reason: '58.3% > 50% minimum' }
    ]
  }
];

export function StrategyDashboard() {
  const { user } = useAuth();
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedStrategy, setSelectedStrategy] = useState(mockStrategies[0]);

  const filteredStrategies = mockStrategies.filter(strategy =>
    strategy.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    strategy.symbol.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(value);
  };

  const formatPercent = (value: number) => {
    return `${value.toFixed(1)}%`;
  };

  const getStatusBadge = (status: string) => {
    const variants = {
      active: 'default',
      paused: 'secondary',
      stopped: 'destructive'
    } as const;
    
    return <Badge variant={variants[status as keyof typeof variants] || 'default'}>{status}</Badge>;
  };

  const getProfitColor = (value: number) => {
    return value >= 0 ? 'text-green-600' : 'text-red-600';
  };

  const lotSizeRecommendations = [
    { risk: 'Low Risk', lotSize: 0.01, description: 'Conservative approach with minimal risk' },
    { risk: 'Medium Risk', lotSize: 0.05, description: 'Balanced risk-reward ratio' },
    { risk: 'Full Risk', lotSize: 0.10, description: 'Maximum recommended position size' }
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="flex items-center gap-2">
          📈 Strategy Dashboard
        </h1>
        {user?.role === 'guest' && (
          <Alert className="max-w-md">
            <Info className="h-4 w-4" />
            <AlertDescription>
              Register to access downloads and portfolio features!
            </AlertDescription>
          </Alert>
        )}
      </div>

      {/* Search & Filter */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center space-x-2">
            <Search className="h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search strategies..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="max-w-md"
            />
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Strategies Table */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Strategies Performance</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Rank</TableHead>
                    <TableHead>Strategy</TableHead>
                    <TableHead>Symbol</TableHead>
                    <TableHead>Net Profit</TableHead>
                    <TableHead>Max DD</TableHead>
                    <TableHead>Trades</TableHead>
                    <TableHead>Score</TableHead>
                    <TableHead>Win Rate</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredStrategies.map((strategy) => (
                    <TableRow 
                      key={strategy.id}
                      className={`cursor-pointer hover:bg-muted/50 ${selectedStrategy.id === strategy.id ? 'bg-muted' : ''}`}
                      onClick={() => setSelectedStrategy(strategy)}
                    >
                      <TableCell className="font-medium">#{strategy.rank}</TableCell>
                      <TableCell className="font-medium">{strategy.name}</TableCell>
                      <TableCell>{strategy.symbol}</TableCell>
                      <TableCell className={getProfitColor(strategy.netProfit)}>
                        {formatCurrency(strategy.netProfit)}
                      </TableCell>
                      <TableCell className={getProfitColor(strategy.maxDD)}>
                        {formatCurrency(strategy.maxDD)}
                      </TableCell>
                      <TableCell>{strategy.totalTrades}</TableCell>
                      <TableCell>{strategy.score}</TableCell>
                      <TableCell>{formatPercent(strategy.winRate)}</TableCell>
                      <TableCell>{getStatusBadge(strategy.status)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>

        {/* Strategy Detail Panel */}
        {selectedStrategy && (
          <>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  {selectedStrategy.name}
                  {getStatusBadge(selectedStrategy.status)}
                </CardTitle>
                <p className="text-sm text-muted-foreground">
                  {selectedStrategy.symbol} • Strategy #{selectedStrategy.id} • Created {selectedStrategy.createdDate}
                </p>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* KPI Cards */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <DollarSign className="h-4 w-4 text-green-600" />
                      <span className="text-sm font-medium">Net Profit</span>
                    </div>
                    <p className={`text-lg font-bold ${getProfitColor(selectedStrategy.netProfit)}`}>
                      {formatCurrency(selectedStrategy.netProfit)}
                    </p>
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <TrendingDown className="h-4 w-4 text-red-600" />
                      <span className="text-sm font-medium">Max Drawdown</span>
                    </div>
                    <p className={`text-lg font-bold ${getProfitColor(selectedStrategy.maxDD)}`}>
                      {formatCurrency(selectedStrategy.maxDD)}
                    </p>
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <BarChart3 className="h-4 w-4 text-blue-600" />
                      <span className="text-sm font-medium">Total Trades</span>
                    </div>
                    <p className="text-lg font-bold">{selectedStrategy.totalTrades}</p>
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <Target className="h-4 w-4 text-purple-600" />
                      <span className="text-sm font-medium">Score</span>
                    </div>
                    <p className="text-lg font-bold">{selectedStrategy.score}</p>
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <Percent className="h-4 w-4 text-orange-600" />
                      <span className="text-sm font-medium">Win Rate</span>
                    </div>
                    <p className="text-lg font-bold">{formatPercent(selectedStrategy.winRate)}</p>
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <TrendingUp className="h-4 w-4 text-indigo-600" />
                      <span className="text-sm font-medium">Profit Factor</span>
                    </div>
                    <p className="text-lg font-bold">{selectedStrategy.profitFactor}</p>
                  </div>
                </div>

                <Separator />

                {/* Criteria Status */}
                <div className="space-y-3">
                  <h4 className="font-medium">Strategy Criteria Status</h4>
                  {selectedStrategy.criteriaStatus.map((criteria, index) => (
                    <div key={index} className="flex items-start gap-2">
                      {criteria.passed ? (
                        <CheckCircle className="h-4 w-4 text-green-600 mt-0.5" />
                      ) : (
                        <XCircle className="h-4 w-4 text-red-600 mt-0.5" />
                      )}
                      <div>
                        <p className="text-sm font-medium">{criteria.name}</p>
                        <p className="text-xs text-muted-foreground">{criteria.reason}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Artifacts Section */}
            <Card>
              <CardHeader>
                <CardTitle>Strategy Artifacts</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <h4 className="font-medium">Download Files</h4>
                  {selectedStrategy.hasSetFile ? (
                    <Button variant="outline" size="sm" disabled={user?.role === 'guest'}>
                      <Download className="h-4 w-4 mr-2" />
                      Download .set file
                    </Button>
                  ) : (
                    <Alert>
                      <Info className="h-4 w-4" />
                      <AlertDescription>Set file not available</AlertDescription>
                    </Alert>
                  )}
                </div>

                <div className="space-y-2">
                  <h4 className="font-medium">Equity Curve</h4>
                  {selectedStrategy.hasEquityCurve ? (
                    <div className="bg-muted rounded-lg p-4 text-center">
                      <BarChart3 className="h-16 w-16 mx-auto text-muted-foreground mb-2" />
                      <p className="text-sm text-muted-foreground">Equity curve visualization would appear here</p>
                    </div>
                  ) : (
                    <Alert>
                      <Info className="h-4 w-4" />
                      <AlertDescription>Equity curve image not available</AlertDescription>
                    </Alert>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* AI Lot Size Recommendation */}
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>AI Lot Size Recommendation</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid md:grid-cols-3 gap-4">
                  {lotSizeRecommendations.map((rec, index) => (
                    <Card key={index} className="border-2">
                      <CardContent className="pt-4">
                        <div className="text-center space-y-2">
                          <h4 className="font-medium">{rec.risk}</h4>
                          <p className="text-2xl font-bold">{rec.lotSize}</p>
                          <p className="text-sm text-muted-foreground">{rec.description}</p>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
                <Alert className="mt-4">
                  <CheckCircle className="h-4 w-4" />
                  <AlertDescription>
                    Based on current market conditions and strategy performance, we recommend starting with Medium Risk (0.05 lots) for optimal risk-reward balance.
                  </AlertDescription>
                </Alert>
              </CardContent>
            </Card>
          </>
        )}
      </div>

      <div className="text-center text-sm text-muted-foreground">
        Do not sell or share your personal info
      </div>
    </div>
  );
}