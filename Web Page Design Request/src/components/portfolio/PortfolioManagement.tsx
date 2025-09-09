import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Badge } from '../ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../ui/table';
import { Textarea } from '../ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../ui/dialog';
import { Alert, AlertDescription } from '../ui/alert';
import { Progress } from '../ui/progress';
import { Checkbox } from '../ui/checkbox';
import { toast } from 'sonner@2.0.3';
import { 
  Briefcase, 
  Plus, 
  Minus, 
  Download, 
  BarChart3,
  Info,
  CheckCircle,
  TrendingUp,
  TrendingDown
} from 'lucide-react';

// Available strategies from Strategy Dashboard
const availableStrategies = [
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
    status: 'active'
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
    status: 'active'
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
    status: 'paused'
  },
  {
    id: 4,
    rank: 4,
    name: 'Scalping Master',
    symbol: 'XAUUSD',
    netProfit: 12500.40,
    maxDD: -1800.20,
    totalTrades: 678,
    recoveryFactor: 6.94,
    score: 75.2,
    winRate: 65.2,
    profitFactor: 1.54,
    expectedPayoff: 18.42,
    distance: 0.30,
    status: 'active'
  }
];

interface Portfolio {
  id: number;
  name: string;
  description: string;
  createdDate: string;
  strategies: any[];
}

export function PortfolioManagement() {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [selectedPortfolio, setSelectedPortfolio] = useState<Portfolio | null>(null);
  const [showCreatePortfolio, setShowCreatePortfolio] = useState(false);
  const [showAddStrategy, setShowAddStrategy] = useState(false);
  const [selectedStrategies, setSelectedStrategies] = useState<number[]>([]);

  // Create portfolio form state
  const [portfolioForm, setPortfolioForm] = useState({
    name: '',
    description: ''
  });

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

  const getStatusBadge = (status: string) => {
    const variants = {
      active: 'default',
      paused: 'secondary',
      stopped: 'destructive'
    } as const;
    
    return <Badge variant={variants[status as keyof typeof variants] || 'default'}>{status}</Badge>;
  };

  const handleCreatePortfolio = () => {
    if (!portfolioForm.name.trim()) {
      toast.error('Portfolio name is required');
      return;
    }

    const newPortfolio: Portfolio = {
      id: Date.now(),
      name: portfolioForm.name,
      description: portfolioForm.description,
      createdDate: new Date().toISOString().split('T')[0],
      strategies: []
    };

    setPortfolios(prev => [...prev, newPortfolio]);
    setSelectedPortfolio(newPortfolio);
    setPortfolioForm({ name: '', description: '' });
    setShowCreatePortfolio(false);
    toast.success('Portfolio created successfully');
  };

  const handleAddStrategies = () => {
    if (!selectedPortfolio || selectedStrategies.length === 0) {
      toast.error('Please select at least one strategy');
      return;
    }

    const strategiesToAdd = availableStrategies.filter(strategy => 
      selectedStrategies.includes(strategy.id) && 
      !selectedPortfolio.strategies.some(existing => existing.id === strategy.id)
    );

    const updatedPortfolio = {
      ...selectedPortfolio,
      strategies: [...selectedPortfolio.strategies, ...strategiesToAdd]
    };

    setPortfolios(prev => prev.map(p => p.id === selectedPortfolio.id ? updatedPortfolio : p));
    setSelectedPortfolio(updatedPortfolio);
    setSelectedStrategies([]);
    setShowAddStrategy(false);
    toast.success(`Added ${strategiesToAdd.length} strategy(ies) to portfolio`);
  };

  const handleRemoveStrategy = (strategyId: number) => {
    if (!selectedPortfolio) return;

    const updatedPortfolio = {
      ...selectedPortfolio,
      strategies: selectedPortfolio.strategies.filter(strategy => strategy.id !== strategyId)
    };

    setPortfolios(prev => prev.map(p => p.id === selectedPortfolio.id ? updatedPortfolio : p));
    setSelectedPortfolio(updatedPortfolio);
    toast.success('Strategy removed from portfolio');
  };

  const calculatePortfolioCorrelation = () => {
    if (!selectedPortfolio || selectedPortfolio.strategies.length < 2) {
      return { overallRisk: 'low', diversification: 'good', recommendation: 'Portfolio has good diversification.' };
    }

    // Simplified correlation calculation based on currency pairs
    const currencies = selectedPortfolio.strategies.map(s => s.symbol);
    const uniqueCurrencies = [...new Set(currencies.join('').split(/(?=[A-Z]{3})/))].filter(c => c.length === 3);
    
    // Calculate risk based on currency overlap
    let riskScore = 0;
    if (currencies.includes('EURUSD') && currencies.includes('GBPUSD')) riskScore += 0.4;
    if (currencies.includes('EURUSD') && currencies.includes('EURGBP')) riskScore += 0.5;
    if (currencies.includes('GBPUSD') && currencies.includes('EURGBP')) riskScore += 0.3;
    
    const diversificationScore = uniqueCurrencies.length / (currencies.length * 2);
    
    let overallRisk = 'low';
    let diversification = 'excellent';
    let recommendation = 'Portfolio has excellent diversification with low correlation risk.';
    
    if (riskScore > 0.3) {
      overallRisk = 'high';
      diversification = 'poor';
      recommendation = 'High correlation detected. Consider adding strategies with different currency pairs for better diversification.';
    } else if (riskScore > 0.1) {
      overallRisk = 'medium';
      diversification = 'moderate';
      recommendation = 'Moderate correlation detected. Portfolio could benefit from additional diversification.';
    }

    return { overallRisk, diversification, recommendation };
  };

  const correlationAnalysis = calculatePortfolioCorrelation();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="flex items-center gap-2">
          💼 Portfolio Management
        </h1>
        <Dialog open={showCreatePortfolio} onOpenChange={setShowCreatePortfolio}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="h-4 w-4 mr-2" />
              Create Portfolio
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create New Portfolio</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="portfolio-name">Portfolio Name</Label>
                <Input
                  id="portfolio-name"
                  value={portfolioForm.name}
                  onChange={(e) => setPortfolioForm(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="Enter portfolio name"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="portfolio-description">Description</Label>
                <Textarea
                  id="portfolio-description"
                  value={portfolioForm.description}
                  onChange={(e) => setPortfolioForm(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="Enter portfolio description"
                  rows={3}
                />
              </div>
              <div className="flex justify-end space-x-2">
                <Button variant="outline" onClick={() => setShowCreatePortfolio(false)}>
                  Cancel
                </Button>
                <Button onClick={handleCreatePortfolio}>
                  Create Portfolio
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Portfolio Selection */}
      {portfolios.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Your Portfolios</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {portfolios.map((portfolio) => (
                <Card 
                  key={portfolio.id} 
                  className={`cursor-pointer transition-colors ${selectedPortfolio?.id === portfolio.id ? 'ring-2 ring-primary' : ''}`}
                  onClick={() => setSelectedPortfolio(portfolio)}
                >
                  <CardContent className="pt-4">
                    <div className="space-y-2">
                      <h4 className="font-medium">{portfolio.name}</h4>
                      <p className="text-sm text-muted-foreground">{portfolio.description}</p>
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>Created: {portfolio.createdDate}</span>
                        <span>{portfolio.strategies.length} strategies</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* No Portfolio Selected */}
      {portfolios.length === 0 && (
        <Card>
          <CardContent className="pt-6">
            <div className="text-center space-y-4">
              <Briefcase className="h-16 w-16 mx-auto text-muted-foreground" />
              <div>
                <h3 className="font-medium">No Portfolios Created</h3>
                <p className="text-sm text-muted-foreground">
                  Create your first portfolio to start managing your trading strategies
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Selected Portfolio Details */}
      {selectedPortfolio && (
        <>
          {/* Portfolio Summary */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                {selectedPortfolio.name}
                <Badge variant="secondary">Created {selectedPortfolio.createdDate}</Badge>
              </CardTitle>
              {selectedPortfolio.description && (
                <p className="text-sm text-muted-foreground">{selectedPortfolio.description}</p>
              )}
            </CardHeader>
            <CardContent>
              <div className="grid md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <BarChart3 className="h-4 w-4 text-orange-600" />
                    <span className="text-sm font-medium">Strategies</span>
                  </div>
                  <p className="text-2xl font-bold">{selectedPortfolio.strategies.length}</p>
                </div>
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <CheckCircle className="h-4 w-4 text-green-600" />
                    <span className="text-sm font-medium">Diversification</span>
                  </div>
                  <p className="text-2xl font-bold capitalize">{correlationAnalysis.diversification}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-6 lg:grid-cols-2">
            {/* Portfolio Strategies */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  Portfolio Strategies
                  <Dialog open={showAddStrategy} onOpenChange={setShowAddStrategy}>
                    <DialogTrigger asChild>
                      <Button size="sm">
                        <Plus className="h-4 w-4 mr-2" />
                        Add Strategy
                      </Button>
                    </DialogTrigger>
                    <DialogContent className="max-w-4xl">
                      <DialogHeader>
                        <DialogTitle>Add Strategies to Portfolio</DialogTitle>
                      </DialogHeader>
                      <div className="space-y-4">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Select</TableHead>
                              <TableHead>Rank</TableHead>
                              <TableHead>Strategy</TableHead>
                              <TableHead>Symbol</TableHead>
                              <TableHead>Score</TableHead>
                              <TableHead>Win Rate</TableHead>
                              <TableHead>Status</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {availableStrategies
                              .filter(strategy => !selectedPortfolio.strategies.some(existing => existing.id === strategy.id))
                              .map((strategy) => (
                              <TableRow key={strategy.id}>
                                <TableCell>
                                  <Checkbox
                                    checked={selectedStrategies.includes(strategy.id)}
                                    onCheckedChange={(checked) => {
                                      if (checked) {
                                        setSelectedStrategies(prev => [...prev, strategy.id]);
                                      } else {
                                        setSelectedStrategies(prev => prev.filter(id => id !== strategy.id));
                                      }
                                    }}
                                  />
                                </TableCell>
                                <TableCell>#{strategy.rank}</TableCell>
                                <TableCell className="font-medium">{strategy.name}</TableCell>
                                <TableCell>{strategy.symbol}</TableCell>
                                <TableCell>{strategy.score}</TableCell>
                                <TableCell>{formatPercent(strategy.winRate)}</TableCell>
                                <TableCell>{getStatusBadge(strategy.status)}</TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                        <div className="flex justify-end space-x-2">
                          <Button variant="outline" onClick={() => setShowAddStrategy(false)}>
                            Cancel
                          </Button>
                          <Button onClick={handleAddStrategies}>
                            Add Selected ({selectedStrategies.length})
                          </Button>
                        </div>
                      </div>
                    </DialogContent>
                  </Dialog>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {selectedPortfolio.strategies.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Strategy</TableHead>
                        <TableHead>Symbol</TableHead>
                        <TableHead>Score</TableHead>
                        <TableHead>Win Rate</TableHead>
                        <TableHead>Max DD</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {selectedPortfolio.strategies.map((strategy) => (
                        <TableRow key={strategy.id}>
                          <TableCell className="font-medium">{strategy.name}</TableCell>
                          <TableCell>{strategy.symbol}</TableCell>
                          <TableCell>{strategy.score}</TableCell>
                          <TableCell>{formatPercent(strategy.winRate)}</TableCell>
                          <TableCell className={getProfitColor(strategy.maxDD)}>
                            {formatCurrency(strategy.maxDD)}
                          </TableCell>
                          <TableCell>{getStatusBadge(strategy.status)}</TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <Button variant="ghost" size="sm">
                                <Download className="h-4 w-4" />
                              </Button>
                              <Button 
                                variant="ghost" 
                                size="sm"
                                onClick={() => handleRemoveStrategy(strategy.id)}
                              >
                                <Minus className="h-4 w-4" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <div className="text-center py-8">
                    <BarChart3 className="h-12 w-12 mx-auto text-muted-foreground mb-2" />
                    <p className="text-sm text-muted-foreground">
                      No strategies added yet. Click "Add Strategy" to get started.
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Portfolio Correlation Assessment */}
            <Card>
              <CardHeader>
                <CardTitle>Portfolio Correlation Assessment</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <span className="text-sm font-medium text-muted-foreground">Overall Risk</span>
                    <div className="flex items-center gap-2">
                      <div className={`w-3 h-3 rounded-full ${
                        correlationAnalysis.overallRisk === 'high' ? 'bg-red-500' :
                        correlationAnalysis.overallRisk === 'medium' ? 'bg-yellow-500' : 'bg-green-500'
                      }`} />
                      <span className="font-medium capitalize">{correlationAnalysis.overallRisk}</span>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <span className="text-sm font-medium text-muted-foreground">Diversification</span>
                    <div className="flex items-center gap-2">
                      <div className={`w-3 h-3 rounded-full ${
                        correlationAnalysis.diversification === 'poor' ? 'bg-red-500' :
                        correlationAnalysis.diversification === 'moderate' ? 'bg-yellow-500' : 'bg-green-500'
                      }`} />
                      <span className="font-medium capitalize">{correlationAnalysis.diversification}</span>
                    </div>
                  </div>
                </div>

                {selectedPortfolio.strategies.length > 0 && (
                  <div className="space-y-2">
                    <span className="text-sm font-medium">Currency Exposure</span>
                    <div className="space-y-1">
                      {[...new Set(selectedPortfolio.strategies.map(s => s.symbol))].map(symbol => (
                        <div key={symbol} className="flex justify-between text-sm">
                          <span>{symbol}</span>
                          <span>{selectedPortfolio.strategies.filter(s => s.symbol === symbol).length} strategy(ies)</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <Alert>
                  <Info className="h-4 w-4" />
                  <AlertDescription>
                    {correlationAnalysis.recommendation}
                  </AlertDescription>
                </Alert>
              </CardContent>
            </Card>
          </div>
        </>
      )}

      <div className="text-center text-sm text-muted-foreground">
        Risk Disclaimer: Trading involves substantial risk and may result in losses. Past performance does not guarantee future results.
      </div>
    </div>
  );
}