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
  templateUrl: './policy-editor.component.component.html',
  styleUrls: ['./policy-editor.component.component.scss'],
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
