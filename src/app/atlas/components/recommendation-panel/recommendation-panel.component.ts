/**
 * ATLAS Recommendation Panel Component
 * View and manage hedge recommendations
 */
import { Component, OnInit } from '@angular/core';
import {
  AtlasApiService,
  HedgeRecommendation
} from '../../services/atlas-api.service';

@Component({
  selector: 'app-recommendation-panel',
  templateUrl: './recommendation-panel.component.component.html',
  styleUrls: ['./recommendation-panel.component.component.scss'],
})
export class RecommendationPanelComponent implements OnInit {
  recommendations: HedgeRecommendation[] = [];
  summary: any = null;
  loading = false;

  filters = {
    status: '',
    urgency: '',
    action: ''
  };

  showReject = false;
  rejectingRec: HedgeRecommendation | null = null;
  rejectReason = '';

  constructor(private atlasApi: AtlasApiService) {}

  ngOnInit() {
    this.loadRecommendations();
    this.loadSummary();
  }

  loadRecommendations() {
    this.loading = true;
    const params: any = {};
    if (this.filters.status) params.status = this.filters.status;
    if (this.filters.urgency) params.urgency = this.filters.urgency;
    if (this.filters.action) params.action = this.filters.action;

    this.atlasApi.getRecommendations(params).subscribe({
      next: (data) => {
        this.recommendations = data;
        this.loading = false;
      },
      error: (err) => {
        console.error('Error loading recommendations:', err);
        this.loading = false;
      }
    });
  }

  loadSummary() {
    this.atlasApi.getRecommendationsSummary().subscribe({
      next: (data) => this.summary = data,
      error: (err) => console.error('Error loading summary:', err)
    });
  }

  generateRecommendations() {
    this.atlasApi.generateRecommendations().subscribe({
      next: () => {
        this.loadRecommendations();
        this.loadSummary();
      },
      error: (err) => console.error('Error generating recommendations:', err)
    });
  }

  formatAction(action: string): string {
    const actions: { [key: string]: string } = {
      'hedge_now': 'Hedge Now',
      'hedge_partial': 'Partial Hedge',
      'wait': 'Wait',
      'review': 'Review'
    };
    return actions[action] || action;
  }

  accept(rec: HedgeRecommendation) {
    this.atlasApi.createOrderFromRecommendation(rec.id).subscribe({
      next: () => {
        this.loadRecommendations();
        this.loadSummary();
      },
      error: (err) => console.error('Error accepting recommendation:', err)
    });
  }

  showRejectModal(rec: HedgeRecommendation) {
    this.rejectingRec = rec;
    this.rejectReason = '';
    this.showReject = true;
  }

  confirmReject() {
    if (!this.rejectingRec) return;

    this.atlasApi.rejectRecommendation(this.rejectingRec.id, this.rejectReason).subscribe({
      next: () => {
        this.showReject = false;
        this.rejectingRec = null;
        this.loadRecommendations();
        this.loadSummary();
      },
      error: (err) => console.error('Error rejecting recommendation:', err)
    });
  }

  closeRejectModal(event: Event) {
    if (event.target === event.currentTarget) {
      this.showReject = false;
    }
  }
}
