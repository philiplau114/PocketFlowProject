import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Badge } from '../ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../ui/table';
import { Separator } from '../ui/separator';
import { Alert, AlertDescription } from '../ui/alert';
import { Slider } from '../ui/slider';
import { Progress } from '../ui/progress';
import { 
  Briefcase, 
  Plus, 
  Minus, 
  Download, 
  TrendingUp, 
  AlertTriangle,
  BarChart3,
  Target,
  DollarSign,
  Info
} from 'lucide-react';

// Mock portfolio data
const mockPortfolio = {
  id: 1,
  name: 'Conservative Growth Portfolio',
  createdDate: '2024-01-15',
  totalValue: 50000,
  currentPL: 2850.75,
  strategies: [
    {
      id: 1,
      name: 'Momentum Scalper Pro',
      symbol: 'EURUSD',
      allocation: 40,
      netProfit: 1520.30,
      maxDD: -250.15,
      lotSize: 0.04,
      correlation: 0.15
    },
    {
      id: 2,
      name: 'Grid Master 2.0',
      symbol: 'GBPUSD',
      allocation: 35,
      netProfit: 980.45,
      maxDD: -180.25,
      lotSize: 0.035,
      correlation: 0.32
    },
    {
      id: 3,
      name: 'Trend Follower Elite',
      symbol: 'USDJPY',
      allocation: 25,
      netProfit: 350.00,
      maxDD: -120.50,
      lotSize: 0.025,
      correlation: -0.08
    }
  ]
};

const correlationMatrix = [
  { pair: 'EURUSD-GBPUSD', correlation: 0.76, risk: 'high' },
  { pair: 'EURUSD-USDJPY', correlation: -0.12, risk: 'low' },
  { pair: 'GBPUSD-USDJPY', correlation: 0.23, risk: 'medium' }
];

export function PortfolioManagement() {
  const [portfolio, setPortfolio] = useState(mockPortfolio);
  const [riskLevel, setRiskLevel] = useState([5]); // 1-10 scale
  const [accountBalance, setAccountBalance] = useState(50000);

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(value);
  };

  const formatPercent = (value: number) => {
    return `${value.toFixed(1)}%`;
  };

  const getProfitColor = (value: number) => {
    return value >= 0 ? 'text-green-600' : 'text-red-600';
  };

  const getCorrelationRisk = (risk: string) => {
    const colors = {
      low: 'text-green-600',
      medium: 'text-yellow-600',
      high: 'text-red-600'
    };
    return colors[risk as keyof typeof colors] || 'text-gray-600';
  };

  const totalAllocation = portfolio.strategies.reduce((sum, strategy) => sum + strategy.allocation, 0);
  const portfolioReturn = (portfolio.currentPL / portfolio.totalValue) * 100;

  const monteCarloResults = {
    expectedReturn: 12.5,
    worstCase: -8.2,
    bestCase: 28.7,
    sharpeRatio: 1.45,
    maxDrawdown: 15.3
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="flex items-center gap-2">
          💼 Portfolio Management
        </h1>
        <Button>
          <Plus className="h-4 w-4 mr-2" />
          Add Strategy
        </Button>
      </div>

      {/* Portfolio Summary */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            {portfolio.name}
            <Badge variant="secondary">Created {portfolio.createdDate}</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-4 gap-4">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <DollarSign className="h-4 w-4 text-blue-600" />
                <span className="text-sm font-medium">Total Value</span>
              </div>
              <p className="text-2xl font-bold">{formatCurrency(portfolio.totalValue)}</p>
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-green-600" />
                <span className="text-sm font-medium">Current P&L</span>
              </div>
              <p className={`text-2xl font-bold ${getProfitColor(portfolio.currentPL)}`}>
                {formatCurrency(portfolio.currentPL)}
              </p>
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Target className="h-4 w-4 text-purple-600" />
                <span className="text-sm font-medium">Return</span>
              </div>
              <p className={`text-2xl font-bold ${getProfitColor(portfolioReturn)}`}>
                {formatPercent(portfolioReturn)}
              </p>
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-orange-600" />
                <span className="text-sm font-medium">Strategies</span>
              </div>
              <p className="text-2xl font-bold">{portfolio.strategies.length}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Portfolio Strategies */}
        <Card>
          <CardHeader>
            <CardTitle>Portfolio Strategies</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {portfolio.strategies.map((strategy) => (
                <div key={strategy.id} className="border rounded-lg p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="font-medium">{strategy.name}</h4>
                    <div className="flex items-center gap-2">
                      <Button variant="ghost" size="sm">
                        <Download className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="sm">
                        <Minus className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-muted-foreground">Symbol:</span>
                      <span className="ml-2 font-medium">{strategy.symbol}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Allocation:</span>
                      <span className="ml-2 font-medium">{strategy.allocation}%</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Net Profit:</span>
                      <span className={`ml-2 font-medium ${getProfitColor(strategy.netProfit)}`}>
                        {formatCurrency(strategy.netProfit)}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Lot Size:</span>
                      <span className="ml-2 font-medium">{strategy.lotSize}</span>
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span>Allocation</span>
                      <span>{strategy.allocation}%</span>
                    </div>
                    <Progress value={strategy.allocation} className="h-2" />
                  </div>
                </div>
              ))}
              
              <div className="border-t pt-4">
                <div className="flex justify-between items-center">
                  <span className="font-medium">Total Allocation</span>
                  <span className={`font-bold ${totalAllocation === 100 ? 'text-green-600' : 'text-red-600'}`}>
                    {totalAllocation}%
                  </span>
                </div>
                {totalAllocation !== 100 && (
                  <Alert className="mt-2">
                    <AlertTriangle className="h-4 w-4" />
                    <AlertDescription>
                      Portfolio allocation should total 100%. Currently {totalAllocation}%.
                    </AlertDescription>
                  </Alert>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Currency Correlation Assessment */}
        <Card>
          <CardHeader>
            <CardTitle>Currency Correlation Assessment</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Currency Pair</TableHead>
                    <TableHead>Correlation</TableHead>
                    <TableHead>Risk</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {correlationMatrix.map((item, index) => (
                    <TableRow key={index}>
                      <TableCell className="font-medium">{item.pair}</TableCell>
                      <TableCell>{item.correlation}</TableCell>
                      <TableCell>
                        <Badge 
                          variant={item.risk === 'high' ? 'destructive' : item.risk === 'medium' ? 'secondary' : 'default'}
                        >
                          {item.risk}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              <Alert>
                <Info className="h-4 w-4" />
                <AlertDescription>
                  High correlation between EURUSD and GBPUSD increases portfolio risk. Consider rebalancing for better diversification.
                </AlertDescription>
              </Alert>
            </div>
          </CardContent>
        </Card>

        {/* Position Sizing */}
        <Card>
          <CardHeader>
            <CardTitle>Position Sizing & Risk Management</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="account-balance">Account Balance</Label>
              <Input
                id="account-balance"
                type="number"
                value={accountBalance}
                onChange={(e) => setAccountBalance(Number(e.target.value))}
              />
            </div>

            <div className="space-y-2">
              <Label>Risk Level: {riskLevel[0]}/10</Label>
              <Slider
                value={riskLevel}
                onValueChange={setRiskLevel}
                max={10}
                min={1}
                step={1}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Conservative</span>
                <span>Aggressive</span>
              </div>
            </div>

            <Separator />

            <div className="space-y-3">
              <h4 className="font-medium">Recommended Position Sizes</h4>
              {portfolio.strategies.map((strategy) => (
                <div key={strategy.id} className="flex justify-between items-center">
                  <span className="text-sm">{strategy.symbol}</span>
                  <span className="font-medium">
                    {(strategy.lotSize * (riskLevel[0] / 5)).toFixed(3)} lots
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Monte Carlo Risk Assessment */}
        <Card>
          <CardHeader>
            <CardTitle>Monte Carlo Risk Assessment</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <span className="text-sm text-muted-foreground">Expected Return</span>
                <p className="text-lg font-bold text-green-600">{formatPercent(monteCarloResults.expectedReturn)}</p>
              </div>
              <div className="space-y-1">
                <span className="text-sm text-muted-foreground">Worst Case</span>
                <p className="text-lg font-bold text-red-600">{formatPercent(monteCarloResults.worstCase)}</p>
              </div>
              <div className="space-y-1">
                <span className="text-sm text-muted-foreground">Best Case</span>
                <p className="text-lg font-bold text-green-600">{formatPercent(monteCarloResults.bestCase)}</p>
              </div>
              <div className="space-y-1">
                <span className="text-sm text-muted-foreground">Sharpe Ratio</span>
                <p className="text-lg font-bold">{monteCarloResults.sharpeRatio}</p>
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Max Expected Drawdown</span>
                <span>{formatPercent(monteCarloResults.maxDrawdown)}</span>
              </div>
              <Progress value={monteCarloResults.maxDrawdown} className="h-2" />
            </div>

            <div className="bg-muted rounded-lg p-4 text-center">
              <BarChart3 className="h-16 w-16 mx-auto text-muted-foreground mb-2" />
              <p className="text-sm text-muted-foreground">Monte Carlo simulation chart would appear here</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Export Portfolio */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-medium">Export Portfolio Report</h3>
              <p className="text-sm text-muted-foreground">
                Download a comprehensive analysis of your portfolio performance and risk metrics
              </p>
            </div>
            <Button>
              <Download className="h-4 w-4 mr-2" />
              Export Report
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="text-center text-sm text-muted-foreground">
        Risk Disclaimer: Trading involves substantial risk and may result in losses. Past performance does not guarantee future results.
      </div>
    </div>
  );
}