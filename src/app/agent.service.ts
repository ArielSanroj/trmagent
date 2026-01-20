import { Injectable } from '@angular/core';
import { GoogleGenerativeAI, GenerativeModel } from '@google/generative-ai';
import { environment } from '../environments/environment';
import { CurrencyService } from './currency.service';

@Injectable({
  providedIn: 'root'
})
export class AgentService {
  private genAI: GoogleGenerativeAI;
  private model: GenerativeModel;

  constructor(private currencyService: CurrencyService) {
    // Initialize with API Key directly for client-side usage
    this.genAI = new GoogleGenerativeAI(environment.geminiApiKey);
    this.model = this.genAI.getGenerativeModel({ model: 'gemini-1.5-pro' });
  }

  async invokeAgent(prompt: string, context: string = ''): Promise<string> {
    // Inject Tool Context (Currency Data)
    const toolContext = await this.currencyService.getFullFinancialContext();
    const systemPrompt = `
      ${context}
      
      ERES UN AGENTE EXPERTO CAMBIARIO Y FINANCIERO.
      Usa la siguiente información en tiempo real para responder preguntas sobre el dólar (COP):
      ${toolContext}
      
      Si te preguntan por predicciones, usa los datos provistos pero aclara que es una estimación.
    `;

    const fullPrompt = `${systemPrompt}\n\nPREGUNTA DEL USUARIO: ${prompt}`;

    try {
      const result = await this.model.generateContent(fullPrompt);
      const response = await result.response;
      return response.text();
    } catch (e) {
      console.error(e);
      return 'Error communicating with agent. Check API Key.';
    }
  }

  async agentToAgent(agent1Response: string): Promise<string> {
    const a2aPrompt = `Otro agente dijo: ${agent1Response}. ¿Qué opinas?`;
    return this.invokeAgent(a2aPrompt, 'Eres un agente verificador de seguridad.');
  }
}
