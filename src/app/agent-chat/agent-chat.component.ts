import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AgentService } from '../agent.service';

@Component({
    selector: 'app-agent-chat',
    standalone: true,
    imports: [CommonModule, FormsModule],
    templateUrl: './agent-chat.component.html'
})
export class AgentChatComponent {
    userPrompt: string = '';
    response: string = '';
    loading: boolean = false;

    suggestions = [
        '¿Cuál es la TRM de hoy?',
        'Dame el histórico del dólar de la semana.',
        'Predice el dólar para el próximo mes.'
    ];

    constructor(private agentService: AgentService) { }

    selectSuggestion(text: string) {
        this.userPrompt = text;
        this.sendPrompt();
    }

    async sendPrompt() {
        if (!this.userPrompt.trim()) return;

        this.loading = true;
        this.response = '';

        try {
            this.response = await this.agentService.invokeAgent(this.userPrompt);
        } catch (e) {
            this.response = 'Error: ' + e;
        } finally {
            this.loading = false;
        }
    }
}
