import axios from 'axios';
import type { 
  SearchResult, 
  MarketData, 
  OHLCV, 
  TechnicalAnalysis, 
  NewsItem, 
  TradeSignal,
  DashboardData,
  WhaleTransaction,
  ExchangeFlow,
  AgentOutput
} from '@/types';

// API base URL - change this to your backend URL
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Search assets
export const searchAssets = async (query: string, assetType?: string): Promise<SearchResult[]> => {
  const response = await api.get('/assets/search', {
    params: { query, asset_type: assetType }
  });
  return response.data.results;
};

// Get asset overview
export const getAssetOverview = async (symbol: string): Promise<{ symbol: string; asset_type: string; market_data: MarketData }> => {
  const response = await api.get(`/assets/${symbol}/overview`);
  return response.data;
};

// Get chart data
export const getChartData = async (symbol: string, timeframe: string = '1d', days: number = 30): Promise<OHLCV[]> => {
  const response = await api.get(`/assets/${symbol}/chart`, {
    params: { timeframe, days }
  });
  return response.data.data;
};

// Get technical analysis
export const getTechnicals = async (symbol: string, timeframe: string = '1d'): Promise<TechnicalAnalysis> => {
  const response = await api.get(`/assets/${symbol}/technicals`, {
    params: { timeframe }
  });
  return response.data;
};

// Get asset news
export const getAssetNews = async (symbol: string, limit: number = 20): Promise<NewsItem[]> => {
  const response = await api.get(`/assets/${symbol}/news`, {
    params: { limit }
  });
  return response.data.news;
};

// Get global news
export const getGlobalNews = async (limit: number = 50): Promise<NewsItem[]> => {
  const response = await api.get('/global/news', {
    params: { limit }
  });
  return response.data.news;
};

// Get global macro intelligence
export const getGlobalMacro = async (limit: number = 100): Promise<Record<string, any>> => {
  const response = await api.get('/global/macro', {
    params: { limit }
  });
  return response.data;
};

// Get global geopolitical intelligence
export const getGlobalGeopolitics = async (limit: number = 100): Promise<Record<string, any>> => {
  const response = await api.get('/global/geopolitics', {
    params: { limit }
  });
  return response.data;
};

// Get whale/flow data
export const getFlowData = async (symbol: string): Promise<{
  symbol: string;
  transactions: WhaleTransaction[];
  exchange_flows: ExchangeFlow[];
  accumulation_trend: Record<string, any>;
}> => {
  const response = await api.get(`/assets/${symbol}/flow`);
  return response.data;
};

// Get trading signal
export const getSignal = async (symbol: string): Promise<TradeSignal> => {
  const response = await api.get(`/assets/${symbol}/signal`);
  return response.data;
};

// Get dashboard data
export const getDashboardData = async (): Promise<DashboardData> => {
  const response = await api.get('/dashboard');
  return response.data;
};

// Get agent status
export const getAgentStatus = async (): Promise<{ agents: AgentOutput[]; timestamp: string }> => {
  const response = await api.get('/agents');
  return response.data;
};

// Run specific agent
export const runAgent = async (agentName: string, context: Record<string, any>): Promise<AgentOutput> => {
  const response = await api.post(`/agents/${agentName}/run`, context);
  return response.data;
};

// Get specific agent status
export const getSingleAgentStatus = async (agentName: string): Promise<Record<string, any>> => {
  const response = await api.get(`/agents/${agentName}/status`);
  return response.data;
};

// Health check
export const healthCheck = async (): Promise<{ status: string; version: string }> => {
  const response = await api.get('/system/health');
  return response.data;
};

export default api;
