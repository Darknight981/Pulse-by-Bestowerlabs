import { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, Activity, Newspaper, Globe, AlertTriangle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { getDashboardData } from '@/lib/api';
import type { DashboardData, SearchResult } from '@/types';

interface DashboardProps {
  onAssetSelect: (asset: SearchResult) => void;
}

export default function Dashboard({ onAssetSelect }: DashboardProps) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const dashboardData = await getDashboardData();
        setData(dashboardData);
      } catch (err) {
        setError('Failed to load dashboard data');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 1000); // Refresh every second
    return () => clearInterval(interval);
  }, []);

  const handleAssetClick = (symbol: string) => {
    const asset: SearchResult = {
      symbol,
      name: symbol,
      asset_type: 'crypto',
      exchange: 'Multiple'
    };
    onAssetSelect(asset);
  };

  const getSentimentColor = (label: string) => {
    switch (label) {
      case 'extreme_fear':
      case 'fear':
        return 'text-red-500';
      case 'greed':
      case 'extreme_greed':
        return 'text-green-500';
      default:
        return 'text-yellow-500';
    }
  };

  const getRiskColor = (level: string) => {
    switch (level) {
      case 'low':
        return 'bg-green-500';
      case 'moderate':
        return 'bg-yellow-500';
      case 'elevated':
        return 'bg-orange-500';
      case 'high':
      case 'severe':
        return 'bg-red-500';
      default:
        return 'bg-gray-500';
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <Card key={i}>
              <CardContent className="p-6">
                <Skeleton className="h-4 w-24 mb-2" />
                <Skeleton className="h-8 w-32" />
              </CardContent>
            </Card>
          ))}
        </div>
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <AlertTriangle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <p className="text-lg font-semibold">{error}</p>
          <p className="text-muted-foreground">Please try again later</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Market Sentiment */}
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Market Sentiment</p>
                <p className={`text-2xl font-bold ${getSentimentColor(data?.market_sentiment?.label || 'neutral')}`}>
                  {data?.market_sentiment?.label?.replace('_', ' ') || 'Neutral'}
                </p>
              </div>
              <Activity className="h-8 w-8 text-muted-foreground" />
            </div>
            <div className="mt-2">
              <div className="text-sm">Fear & Greed: {data?.market_sentiment?.fear_greed_index || 50}/100</div>
            </div>
          </CardContent>
        </Card>

        {/* Crypto Market Cap */}
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Global Market Cap</p>
                <p className="text-2xl font-bold">
                  ${((data?.global_data?.total_market_cap_usd || 0) / 1e12).toFixed(2)}T
                </p>
              </div>
              <Globe className="h-8 w-8 text-muted-foreground" />
            </div>
            <div className="mt-2">
              <span className={`text-sm ${(data?.global_data?.market_cap_change_24h || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                {(data?.global_data?.market_cap_change_24h || 0) >= 0 ? '+' : ''}
                {(data?.global_data?.market_cap_change_24h || 0).toFixed(2)}%
              </span>
            </div>
          </CardContent>
        </Card>

        {/* BTC Dominance */}
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">BTC Dominance</p>
                <p className="text-2xl font-bold">
                  {(data?.global_data?.btc_dominance || 0).toFixed(1)}%
                </p>
              </div>
              <div className="h-8 w-8 rounded-full bg-orange-500 flex items-center justify-center text-white font-bold text-xs">
                B
              </div>
            </div>
            <div className="mt-2">
              <span className="text-sm text-muted-foreground">
                ETH: {(data?.global_data?.eth_dominance || 0).toFixed(1)}%
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Geopolitical Risk */}
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Geo Risk</p>
                <p className="text-2xl font-bold capitalize">
                  {data?.geopolitical_risk?.risk_level || 'Moderate'}
                </p>
              </div>
              <AlertTriangle className="h-8 w-8 text-muted-foreground" />
            </div>
            <div className="mt-2">
              <div className={`h-2 w-full rounded-full ${getRiskColor(data?.geopolitical_risk?.risk_level || 'moderate')}`} 
                   style={{ width: `${(data?.geopolitical_risk?.overall_risk || 5) * 10}%` }} />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Top Movers */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5" />
              Top Movers (24h)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {data?.top_movers?.slice(0, 10).map((mover) => (
                <div 
                  key={mover.symbol}
                  onClick={() => handleAssetClick(mover.symbol)}
                  className="flex items-center justify-between p-3 rounded-lg hover:bg-accent cursor-pointer transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div className="font-semibold">{mover.symbol}</div>
                    <div className="text-sm text-muted-foreground">
                      ${mover.price?.toLocaleString()}
                    </div>
                  </div>
                  <div className={`flex items-center gap-1 ${
                    (mover.change_percent_24h || 0) >= 0 ? 'text-green-500' : 'text-red-500'
                  }`}>
                    {(mover.change_percent_24h || 0) >= 0 ? (
                      <TrendingUp className="h-4 w-4" />
                    ) : (
                      <TrendingDown className="h-4 w-4" />
                    )}
                    <span className="font-mono">
                      {(mover.change_percent_24h || 0).toFixed(2)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Latest News */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Newspaper className="h-5 w-5" />
              Latest News
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 max-h-96 overflow-auto">
              {data?.latest_news?.slice(0, 10).map((news) => (
                <div key={news.id} className="border-b last:border-b-0 pb-3 last:pb-0">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium line-clamp-2">{news.title}</p>
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <Badge variant="outline" className="text-xs">{news.source}</Badge>
                    <Badge 
                      className={`text-xs ${
                        news.sentiment_label === 'positive' ? 'bg-green-500' :
                        news.sentiment_label === 'negative' ? 'bg-red-500' :
                        'bg-gray-500'
                      }`}
                    >
                      {news.sentiment_label}
                    </Badge>
                    {news.impact_score > 7 && (
                      <Badge variant="destructive" className="text-xs">High Impact</Badge>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Trending Assets */}
      <Card>
        <CardHeader>
          <CardTitle>Trending Assets</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {data?.trending_assets?.map((asset) => (
              <Badge 
                key={asset}
                variant="secondary"
                className="cursor-pointer hover:bg-primary hover:text-primary-foreground"
                onClick={() => handleAssetClick(asset)}
              >
                {asset}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
