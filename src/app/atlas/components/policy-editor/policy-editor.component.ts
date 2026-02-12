/**
 * ATLAS Policy Editor Component
 * Configure hedge coverage policies
 */
import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import {
  AtlasApiService,
  HedgePolicy,
  PolicySimulationResult
} from '../../services/atlas-api.service';

@Component({
  selector: 'app-policy-editor',
  template: `
    <div class="policy-editor">
      <header class="page-header">
        <h1>Hedge Policies</h1>
        <button class="btn btn-primary" (click)="showCreateModal = true">+ New Policy</button>
      </header>

      <!-- Policies List -->
      <section class="policies-list">
        <div class="policy-card" *ngFor="let policy of policies" [class.default]="policy.is_default">
          <div class="policy-header">
            <h3>{{ policy.name }}</h3>
            <span class="default-badge" *ngIf="policy.is_default">Default</span>
          </div>
          <p class="policy-description">{{ policy.description || 'No description' }}</p>

          <div class="coverage-rules">
            <h4>Coverage Rules</h4>
            <div class="rules-grid">
              <div class="rule" *ngFor="let rule of getHorizons(policy.coverage_rules)">
                <span class="horizon">{{ rule.horizon }}</span>
                <span class="target">{{ rule.target }}%</span>
              </div>
            </div>
          </div>

          <div class="policy-meta">
            <span *ngIf="policy.exposure_type">Type: {{ policy.exposure_type }}</span>
            <span>Currency: {{ policy.currency }}</span>
            <span *ngIf="policy.min_amount">Min: {{ policy.min_amount | number }}</span>
          </div>

          <div class="policy-actions">
            <button class="btn btn-sm" (click)="simulatePolicy(policy)">Simulate</button>
            <button class="btn btn-sm" (click)="editPolicy(policy)">Edit</button>
            <button class="btn btn-sm" (click)="setAsDefault(policy)" *ngIf="!policy.is_default">Set Default</button>
          </div>
        </div>

        <div class="empty-state" *ngIf="policies.length === 0 && !loading">
          <p>No policies configured. Create your first policy to start generating recommendations.</p>
        </div>
      </section>

      <!-- Simulation Result -->
      <section class="simulation-result" *ngIf="simulationResult">
        <h2>Policy Simulation Result</h2>
        <div class="sim-metrics">
          <div class="metric">
            <span class="label">Total Exposure</span>
            <span class="value">{{ simulationResult.total_exposure | number:'1.0-0' }}</span>
          </div>
          <div class="metric">
            <span class="label">Would Hedge</span>
            <span class="value">{{ simulationResult.would_hedge | number:'1.0-0' }}</span>
          </div>
          <div class="metric">
            <span class="label">Coverage %</span>
            <span class="value">{{ simulationResult.coverage_percentage | number:'1.1-1' }}%</span>
          </div>
          <div class="metric">
            <span class="label">Est. Orders</span>
            <span class="value">{{ simulationResult.estimated_orders }}</span>
          </div>
        </div>
        <button class="btn btn-secondary" (click)="simulationResult = null">Close</button>
      </section>

      <!-- Create/Edit Modal -->
      <div class="modal" *ngIf="showCreateModal" (click)="closeModal($event)">
        <div class="modal-content" (click)="$event.stopPropagation()">
          <h2>{{ editingPolicy ? 'Edit Policy' : 'New Policy' }}</h2>
          <form [formGroup]="policyForm" (ngSubmit)="savePolicy()">
            <div class="form-group">
              <label>Policy Name *</label>
              <input type="text" formControlName="name" placeholder="e.g., Standard Coverage">
            </div>

            <div class="form-group">
              <label>Description</label>
              <textarea formControlName="description" rows="2"></textarea>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label>Exposure Type</label>
                <select formControlName="exposure_type">
                  <option value="">All Types</option>
                  <option value="payable">Payables Only</option>
                  <option value="receivable">Receivables Only</option>
                </select>
              </div>
              <div class="form-group">
                <label>Currency</label>
                <select formControlName="currency">
                  <option value="USD">USD</option>
                  <option value="EUR">EUR</option>
                </select>
              </div>
            </div>

            <div class="form-group">
              <label>Coverage Rules by Horizon</label>
              <div class="rules-editor">
                <div class="rule-row" *ngFor="let h of horizonLabels">
                  <span class="horizon-label">{{ h.label }}</span>
                  <input type="number" [formControlName]="'rule_' + h.key"
                         min="0" max="100" step="5" placeholder="%">
                  <span class="percent">%</span>
                </div>
              </div>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label>Min Amount to Apply</label>
                <input type="number" formControlName="min_amount" step="1000">
              </div>
              <div class="form-group">
                <label>Require Approval Above</label>
                <input type="number" formControlName="require_approval_above" step="10000">
              </div>
            </div>

            <div class="form-group checkbox-group">
              <label>
                <input type="checkbox" formControlName="auto_generate_recommendations">
                Auto-generate recommendations
              </label>
              <label>
                <input type="checkbox" formControlName="is_default">
                Set as default policy
              </label>
            </div>

            <div class="form-actions">
              <button type="button" class="btn btn-secondary" (click)="showCreateModal = false">Cancel</button>
              <button type="submit" class="btn btn-primary" [disabled]="!policyForm.valid">Save</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .policy-editor { padding: 20px; max-width: 1200px; margin: 0 auto; }
    .page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
    .page-header h1 { margin: 0; }

    .btn { padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
    .btn-primary { background: #007bff; color: white; }
    .btn-primary:hover { background: #0056b3; }
    .btn-secondary { background: #6c757d; color: white; }
    .btn-sm { padding: 6px 12px; font-size: 12px; }

    .policies-list { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px; }

    .policy-card { background: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    .policy-card.default { border: 2px solid #007bff; }

    .policy-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
    .policy-header h3 { margin: 0; }
    .default-badge { background: #007bff; color: white; padding: 2px 8px; border-radius: 4px; font-size: 11px; }

    .policy-description { color: #666; font-size: 14px; margin-bottom: 15px; }

    .coverage-rules h4 { margin: 0 0 10px; font-size: 14px; color: #333; }
    .rules-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
    .rule { text-align: center; padding: 10px; background: #f8f9fa; border-radius: 4px; }
    .rule .horizon { display: block; font-size: 11px; color: #666; margin-bottom: 5px; }
    .rule .target { font-size: 18px; font-weight: bold; color: #28a745; }

    .policy-meta { display: flex; gap: 15px; margin: 15px 0; font-size: 12px; color: #666; }

    .policy-actions { display: flex; gap: 10px; }

    .simulation-result { background: white; border-radius: 8px; padding: 20px; margin-top: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    .simulation-result h2 { margin: 0 0 20px; }
    .sim-metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 20px; }
    .metric { text-align: center; }
    .metric .label { display: block; font-size: 12px; color: #666; margin-bottom: 5px; }
    .metric .value { font-size: 24px; font-weight: bold; color: #1a1a2e; }

    .empty-state { grid-column: 1 / -1; text-align: center; padding: 40px; color: #666; }

    .modal { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
    .modal-content { background: white; border-radius: 8px; padding: 30px; width: 100%; max-width: 600px; max-height: 90vh; overflow-y: auto; }
    .modal-content h2 { margin: 0 0 20px; }

    .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
    .form-group { margin-bottom: 15px; }
    .form-group label { display: block; margin-bottom: 5px; font-weight: 500; font-size: 13px; }
    .form-group input, .form-group select, .form-group textarea { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; box-sizing: border-box; }
    .form-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }

    .rules-editor { display: grid; gap: 10px; }
    .rule-row { display: flex; align-items: center; gap: 10px; }
    .horizon-label { width: 100px; font-size: 13px; }
    .rule-row input { width: 80px; }
    .percent { color: #666; }

    .checkbox-group { display: flex; flex-direction: column; gap: 10px; }
    .checkbox-group label { display: flex; align-items: center; gap: 8px; cursor: pointer; }
    .checkbox-group input[type="checkbox"] { width: auto; }
  `]
})
export class PolicyEditorComponent implements OnInit {
  policies: HedgePolicy[] = [];
  loading = false;

  showCreateModal = false;
  editingPolicy: HedgePolicy | null = null;
  policyForm: FormGroup;

  simulationResult: PolicySimulationResult | null = null;

  horizonLabels = [
    { key: '0-30', label: '0-30 Days' },
    { key: '31-60', label: '31-60 Days' },
    { key: '61-90', label: '61-90 Days' },
    { key: '91+', label: '91+ Days' }
  ];

  constructor(
    private atlasApi: AtlasApiService,
    private fb: FormBuilder
  ) {
    this.policyForm = this.fb.group({
      name: ['', Validators.required],
      description: [''],
      exposure_type: [''],
      currency: ['USD'],
      'rule_0-30': [100],
      'rule_31-60': [75],
      'rule_61-90': [50],
      'rule_91+': [25],
      min_amount: [0],
      require_approval_above: [''],
      auto_generate_recommendations: [true],
      is_default: [false]
    });
  }

  ngOnInit() {
    this.loadPolicies();
  }

  loadPolicies() {
    this.loading = true;
    this.atlasApi.getPolicies().subscribe({
      next: (data) => {
        this.policies = data;
        this.loading = false;
      },
      error: (err) => {
        console.error('Error loading policies:', err);
        this.loading = false;
      }
    });
  }

  getHorizons(rules: { [key: string]: number }): { horizon: string; target: number }[] {
    return this.horizonLabels.map(h => ({
      horizon: h.label,
      target: rules[h.key] || 0
    }));
  }

  editPolicy(policy: HedgePolicy) {
    this.editingPolicy = policy;
    this.policyForm.patchValue({
      name: policy.name,
      description: policy.description,
      exposure_type: policy.exposure_type || '',
      currency: policy.currency,
      'rule_0-30': policy.coverage_rules['0-30'] || 0,
      'rule_31-60': policy.coverage_rules['31-60'] || 0,
      'rule_61-90': policy.coverage_rules['61-90'] || 0,
      'rule_91+': policy.coverage_rules['91+'] || 0,
      min_amount: policy.min_amount,
      require_approval_above: policy.require_approval_above,
      auto_generate_recommendations: policy.auto_generate_recommendations,
      is_default: policy.is_default
    });
    this.showCreateModal = true;
  }

  savePolicy() {
    if (!this.policyForm.valid) return;

    const formValue = this.policyForm.value;
    const data: Partial<HedgePolicy> = {
      name: formValue.name,
      description: formValue.description,
      exposure_type: formValue.exposure_type || undefined,
      currency: formValue.currency,
      coverage_rules: {
        '0-30': formValue['rule_0-30'],
        '31-60': formValue['rule_31-60'],
        '61-90': formValue['rule_61-90'],
        '91+': formValue['rule_91+']
      },
      min_amount: formValue.min_amount,
      require_approval_above: formValue.require_approval_above || undefined,
      auto_generate_recommendations: formValue.auto_generate_recommendations,
      is_default: formValue.is_default
    };

    const request = this.editingPolicy
      ? this.atlasApi.updatePolicy(this.editingPolicy.id, data)
      : this.atlasApi.createPolicy(data);

    request.subscribe({
      next: () => {
        this.showCreateModal = false;
        this.editingPolicy = null;
        this.policyForm.reset({
          currency: 'USD',
          'rule_0-30': 100,
          'rule_31-60': 75,
          'rule_61-90': 50,
          'rule_91+': 25,
          auto_generate_recommendations: true
        });
        this.loadPolicies();
      },
      error: (err) => console.error('Error saving policy:', err)
    });
  }

  simulatePolicy(policy: HedgePolicy) {
    this.atlasApi.simulatePolicy(policy.id).subscribe({
      next: (result) => this.simulationResult = result,
      error: (err) => console.error('Error simulating policy:', err)
    });
  }

  setAsDefault(policy: HedgePolicy) {
    this.atlasApi.updatePolicy(policy.id, { is_default: true }).subscribe({
      next: () => this.loadPolicies(),
      error: (err) => console.error('Error setting default:', err)
    });
  }

  closeModal(event: Event) {
    if (event.target === event.currentTarget) {
      this.showCreateModal = false;
      this.editingPolicy = null;
    }
  }
}
