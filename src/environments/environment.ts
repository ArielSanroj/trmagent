export const environment = {
  production: false,

  // Backend API
  apiUrl: 'http://127.0.0.1:8000/api/v1',

  // Google Gemini (for agent chat)
  geminiApiKey: 'TU_API_KEY_AQUI',
  vertexProjectId: 'TU_PROJECT_ID',

  // Feature flags
  enablePaperTrading: true,
  enableRealTrading: false,

  // Trading config
  minConfidence: 0.90,  // 90% confianza minima
  minExpectedReturn: 0.02,  // 2% retorno minimo

  // Refresh intervals (ms)
  trmRefreshInterval: 300000,  // 5 minutos
  signalRefreshInterval: 60000,  // 1 minuto
};
