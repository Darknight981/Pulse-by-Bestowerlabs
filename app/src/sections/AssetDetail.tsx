import { useState, useEffect } from 'react';
import { ArrowLeft, TrendingUp, TrendingDown, Activity, Target, ShieldAlert } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Skeleton } from '@/components/ui/skeleton';
import { 
  getAssetOverview, 
  getChartData, 
  getTechnicals, 
  getAssetNews, 
  getSignal,
  getFlowData
} from '@/lib/api';
import type { SearchResult, OHLCV, TradeSignal, NewsItem } from '@/types';
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  ResponsiveContainer, 
  Tooltip,
  CartesianGrid
} from 'recharts';

interface AssetDetailProps {
  asset: SearchResult;
  onBack: () => void;
}

export default function AssetDetail({ asset, onBack }: AssetDetailProps) {
  const [overview, setOverview] = useState<any>(null);
  const [chartData, setChartData] = useState<OHLCV[]>([]);
  const [technicals, setTechnicals] = useState<any>(null);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [signal, setSignal] = useState<TradeSignal | null>(null);
  const [flowData, setFlowData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [timeframe, setTimeframe] = useState('1d');

  useEffect(() => {
    const fetchFullData = async () => {
      try {
        const [chart, tech, newsData, signalData, flow] = await Promise.all([
          getChartData(asset.symbol, timeframe, 30),
          getTechnicals(asset.symbol, timeframe),
          getAssetNews(asset.symbol, 10),
          getSignal(asset.symbol, "strict"),
          getFlowData(asset.symbol),
        ]);

        setChartData(chart);
        setTechnicals(tech);
        setNews(newsData);
        setSignal(signalData);
        setFlowData(flow);
      } catch (error) {
        console.error('Error fetching asset data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchFullData();
    const interval = setInterval(fetchFullData, 30000);
    return () => clearInterval(interval);
  }, [asset.symbol, timeframe]);

  useEffect(() => {
    const fetchOverview = async () => {
      try {
        const overviewData = await getAssetOverview(asset.symbol);
        setOverview(overviewData);
      } catch (error) {
        console.error('Error fetching live overview:', error);
      }
    };

    fetchOverview();
    const interval = setInterval(fetchOverview, 1000);
    return () => clearInterval(interval);
  }, [asset.symbol]);

  const getSignalColor = (signalType: string) => {
    switch (signalType) {
      case 'strong_buy':
      case 'buy':
        return 'bg-green-500';
      case 'strong_sell':
      case 'sell':
        return 'bg-red-500';
      default:
        return 'bg-yellow-500';
    }
  };

  const getSignalIcon = (signalType: string) => {
    if (signalType.includes('buy')) return <TrendingUp className="h-5 w-5" />;
    if (signalType.includes('sell')) return <TrendingDown className="h-5 w-5" />;
    return <Activity className="h-5 w-5" />;
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" onClick={onBack}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back
        </Button>
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  const marketData = overview?.market_data;
  const backendTimestamp = marketData?.timestamp ? new Date(marketData.timestamp) : null;
  const sourceTimestamp = marketData?.source_timestamp ? new Date(marketData.source_timestamp) : null;
  const freshnessMs = sourceTimestamp ? Date.now() - sourceTimestamp.getTime() : null;
  const isStale = freshnessMs !== null && freshnessMs > 15000;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <Button variant="ghost" onClick={onBack}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Dashboard
        </Button>
        <div className="flex items-center gap-2">
          <Badge variant="outline">{asset.asset_type.replace('_', ' ').toUpperCase()}</Badge>
          <Badge variant="outline">{asset.exchange}</Badge>
        </div>
      </div>

      <Card className="border-yellow-500/40 bg-yellow-500/5">
        <CardContent className="p-4 text-sm">
          <div className="flex items-start gap-2">
            <ShieldAlert className="h-4 w-4 mt-0.5 text-yellow-500" />
            <div>
              <p className="font-semibold">PULSE Beta Intelligence Mode</p>
              <p className="text-muted-foreground">
                Signals are provided for research support. Data quality is enforced in <span className="font-medium">STRICT</span> mode on this screen.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Price Header */}
      <div className="flex items-end justify-between">
        <div>
          <h2 className="text-3xl font-bold">{asset.symbol}</h2>
          <p className="text-muted-foreground">{asset.name}</p>
        </div>
        <div className="text-right">
          <p className="text-3xl font-bold">${marketData?.price?.toLocaleString()}</p>
          <p className={`text-lg ${(marketData?.change_24h || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
            {(marketData?.change_24h || 0) >= 0 ? '+' : ''}
            {(marketData?.change_24h || 0).toFixed(2)}%
          </p>
          <p className={`text-xs ${isStale ? 'text-red-500' : 'text-muted-foreground'}`}>
            Source: {marketData?.source || 'unknown'} ·{" "}
            {sourceTimestamp ? sourceTimestamp.toLocaleTimeString() : 'n/a'}
          </p>
          {backendTimestamp && (
            <p className="text-xs text-muted-foreground">
              Updated: {backendTimestamp.toLocaleTimeString()}
            </p>
          )}
        </div>
      </div>

      {/* AI Signal Card */}
      {signal && (
        <Card className={`border-l-4 ${getSignalColor(signal.signal).replace('bg-', 'border-l-')}`}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {getSignalIcon(signal.signal)}
              AI Trading Signal
              <Badge className={getSignalColor(signal.signal)}>
                {signal.signal.replace('_', ' ').toUpperCase()}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <p className="text-sm text-muted-foreground">Confidence</p>
                <p className="text-xl font-bold">{signal.confidence}%</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Risk Score</p>
                <p className="text-xl font-bold">{signal.risk_score}/10</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Entry Zone</p>
                <p className="text-xl font-bold">
                  ${signal.entry_zone.min.toFixed(2)} - ${signal.entry_zone.max.toFixed(2)}
                </p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Stop Loss</p>
                <p className="text-xl font-bold text-red-500">${signal.stop_loss.toFixed(2)}</p>
              </div>
            </div>
            
            <div className="mt-4">
              <p className="text-sm text-muted-foreground">Take Profit Targets</p>
              <div className="flex gap-2 mt-1">
                {signal.take_profit.map((tp, i) => (
                  <Badge key={i} variant="outline" className="text-green-500">
                    <Target className="h-3 w-3 mr-1" />
                    TP{i + 1}: ${tp.toFixed(2)}
                  </Badge>
                ))}
              </div>
            </div>

            <div className="mt-4">
              <p className="text-sm font-medium">Thesis</p>
              <p className="text-sm text-muted-foreground">{signal.thesis}</p>
            </div>

            {(signal as any).data_quality && (
              <div className="mt-4">
                <p className="text-sm font-medium">Data Quality</p>
                <div className="flex flex-wrap gap-2 mt-1">
                  <Badge variant="outline">Mode: {(signal as any).data_quality.mode?.toUpperCase()}</Badge>
                  <Badge variant="outline">OHLCV: {(signal as any).data_quality.ohlcv_points}</Badge>
                  <Badge variant="outline">News: {(signal as any).data_quality.news_items}</Badge>
                  <Badge variant="outline">Freshness: {(signal as any).data_quality.freshness_score}</Badge>
                  <Badge variant="outline">Agents: {(signal as any).data_quality.agent_count ?? 'n/a'}</Badge>
                </div>
                {((signal as any).data_quality.warnings || []).length > 0 && (
                  <p className="text-xs text-yellow-500 mt-2">
                    Warnings: {((signal as any).data_quality.warnings || []).join(', ')}
                  </p>
                )}
              </div>
            )}

            {signal.supporting_evidence.length > 0 && (
              <div className="mt-4">
                <p className="text-sm font-medium">Supporting Evidence</p>
                <div className="flex flex-wrap gap-2 mt-1">
                  {signal.supporting_evidence.map((evidence, i) => (
                    <Badge key={i} variant="secondary" className="text-xs">
                      {evidence}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Chart and Data Tabs */}
      <Tabs defaultValue="chart" className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="chart">Price Chart</TabsTrigger>
          <TabsTrigger value="technicals">Technicals</TabsTrigger>
          <TabsTrigger value="news">News</TabsTrigger>
          <TabsTrigger value="flow">Flow Data</TabsTrigger>
        </TabsList>

        <TabsContent value="chart" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Price Chart</CardTitle>
                <div className="flex gap-2">
                  {['1h', '1d', '1w'].map((tf) => (
                    <Button
                      key={tf}
                      variant={timeframe === tf ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setTimeframe(tf)}
                    >
                      {tf.toUpperCase()}
                    </Button>
                  ))}
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData}>
                    <defs>
                      <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#8884d8" stopOpacity={0.8}/>
                        <stop offset="95%" stopColor="#8884d8" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis 
                      dataKey="timestamp" 
                      tickFormatter={(value) => new Date(value).toLocaleDateString()}
                    />
                    <YAxis domain={['auto', 'auto']} />
                    <Tooltip 
                      formatter={(value: number) => value?.toFixed(2)}
                      labelFormatter={(label) => new Date(label).toLocaleString()}
                    />
                    <Area 
                      type="monotone" 
                      dataKey="close" 
                      stroke="#8884d8" 
                      fillOpacity={1} 
                      fill="url(#colorPrice)" 
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="technicals" className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {technicals?.indicators && Object.entries(technicals.indicators).map(([key, value]) => (
              <Card key={key}>
                <CardContent className="p-4">
                  <p className="text-sm text-muted-foreground uppercase">{key.replace('_', ' ')}</p>
                  <p className="text-xl font-bold">{(value as number)?.toFixed(2)}</p>
                </CardContent>
              </Card>
            ))}
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Technical Signals</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {technicals?.signals?.map((signal: string, i: number) => (
                  <Badge key={i} variant="outline">{signal}</Badge>
                ))}
              </div>
              <div className="mt-4">
                <p className="text-sm text-muted-foreground">Trend: <span className="font-semibold">{technicals?.trend}</span></p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="news" className="space-y-4">
          <div className="space-y-3">
            {news.map((item) => (
              <Card key={item.id}>
                <CardContent className="p-4">
                  <p className="font-medium">{item.title}</p>
                  {item.summary && (
                    <p className="text-sm text-muted-foreground mt-1">{item.summary}</p>
                  )}
                  <div className="flex items-center gap-2 mt-2">
                    <Badge variant="outline">{item.source}</Badge>
                    <Badge 
                      className={
                        item.sentiment_label === 'positive' ? 'bg-green-500' :
                        item.sentiment_label === 'negative' ? 'bg-red-500' :
                        'bg-gray-500'
                      }
                    >
                      {item.sentiment_label}
                    </Badge>
                    {item.impact_score > 7 && (
                      <Badge variant="destructive">High Impact</Badge>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="flow" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Exchange Flows</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {flowData?.exchange_flows?.map((flow: any) => (
                  <div key={flow.exchange} className="flex items-center justify-between p-3 border rounded">
                    <div className="capitalize font-medium">{flow.exchange}</div>
                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <p className="text-sm text-muted-foreground">Net Flow</p>
                        <p className={`font-mono ${flow.netflow > 0 ? 'text-green-500' : 'text-red-500'}`}>
                          ${(flow.netflow_usd / 1e6).toFixed(1)}M
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {flowData?.accumulation_trend && (
            <Card>
              <CardHeader>
                <CardTitle>Accumulation Trend</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-4">
                  <div>
                    <p className="text-sm text-muted-foreground">Trend</p>
                    <p className="text-xl font-bold capitalize">{flowData.accumulation_trend.trend}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Signal</p>
                    <Badge className={
                      flowData.accumulation_trend.signal === 'bullish' ? 'bg-green-500' :
                      flowData.accumulation_trend.signal === 'bearish' ? 'bg-red-500' :
                      'bg-yellow-500'
                    }>
                      {flowData.accumulation_trend.signal}
                    </Badge>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
