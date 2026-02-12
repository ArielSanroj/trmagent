/**
 * ATLAS Exposure Manager Component
 * Manage FX exposures: list, create, upload CSV
 */
import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import {
  AtlasApiService,
  Exposure,
  ExposureSummary,
  Counterparty,
  ExposureUploadResult
} from '../../services/atlas-api.service';

@Component({
  selector: 'app-exposure-manager',
  templateUrl: './exposure-manager.component.component.html',
  styleUrls: ['./exposure-manager.component.component.scss'],
})
export class ExposureManagerComponent implements OnInit {
  exposures: Exposure[] = [];
  summary: ExposureSummary | null = null;
  counterparties: Counterparty[] = [];
  loading = false;

  filters = {
    exposure_type: '',
    status: '',
    due_date_from: '',
    due_date_to: ''
  };

  // Create/Edit modal
  showCreateModal = false;
  editingExposure: Exposure | null = null;
  exposureForm: FormGroup;

  // Upload modal
  showUploadModal = false;
  selectedFile: File | null = null;
  uploading = false;
  uploadResult: ExposureUploadResult | null = null;
  isDragOver = false;

  constructor(
    private atlasApi: AtlasApiService,
    private fb: FormBuilder
  ) {
    this.exposureForm = this.fb.group({
      exposure_type: ['payable', Validators.required],
      reference: ['', Validators.required],
      amount: ['', [Validators.required, Validators.min(0.01)]],
      currency: ['USD'],
      due_date: ['', Validators.required],
      invoice_date: [''],
      description: [''],
      budget_rate: [''],
      target_rate: ['']
    });
  }

  ngOnInit() {
    this.loadExposures();
    this.loadSummary();
    this.loadCounterparties();
  }

  loadExposures() {
    this.loading = true;
    const params: any = {};
    if (this.filters.exposure_type) params.exposure_type = this.filters.exposure_type;
    if (this.filters.status) params.status = this.filters.status;
    if (this.filters.due_date_from) params.due_date_from = this.filters.due_date_from;
    if (this.filters.due_date_to) params.due_date_to = this.filters.due_date_to;

    this.atlasApi.getExposures(params).subscribe({
      next: (data) => {
        this.exposures = data;
        this.loading = false;
      },
      error: (err) => {
        console.error('Error loading exposures:', err);
        this.loading = false;
      }
    });
  }

  loadSummary() {
    this.atlasApi.getExposureSummary().subscribe({
      next: (data) => this.summary = data,
      error: (err) => console.error('Error loading summary:', err)
    });
  }

  loadCounterparties() {
    this.atlasApi.getCounterparties().subscribe({
      next: (data) => this.counterparties = data,
      error: (err) => console.error('Error loading counterparties:', err)
    });
  }

  formatStatus(status: string): string {
    const statuses: { [key: string]: string } = {
      'open': 'Open',
      'partially_hedged': 'Partial',
      'fully_hedged': 'Hedged',
      'settled': 'Settled',
      'cancelled': 'Cancelled'
    };
    return statuses[status] || status;
  }

  getCoveragePercent(hedged: number, total: number): number {
    return total > 0 ? (hedged / total) * 100 : 0;
  }

  viewExposure(exp: Exposure) {
    // TODO: Implement detail view
    console.log('View exposure:', exp);
  }

  editExposure(exp: Exposure) {
    this.editingExposure = exp;
    this.exposureForm.patchValue({
      exposure_type: exp.exposure_type,
      reference: exp.reference,
      amount: exp.amount,
      currency: exp.currency,
      due_date: exp.due_date,
      invoice_date: exp.invoice_date,
      description: exp.description,
      budget_rate: exp.budget_rate,
      target_rate: exp.target_rate
    });
    this.showCreateModal = true;
  }

  deleteExposure(exp: Exposure) {
    if (confirm(`Cancel exposure ${exp.reference}?`)) {
      this.atlasApi.deleteExposure(exp.id).subscribe({
        next: () => this.loadExposures(),
        error: (err) => console.error('Error cancelling exposure:', err)
      });
    }
  }

  saveExposure() {
    if (!this.exposureForm.valid) return;

    const data = this.exposureForm.value;

    if (this.editingExposure) {
      this.atlasApi.updateExposure(this.editingExposure.id, data).subscribe({
        next: () => {
          this.showCreateModal = false;
          this.editingExposure = null;
          this.exposureForm.reset({ exposure_type: 'payable', currency: 'USD' });
          this.loadExposures();
          this.loadSummary();
        },
        error: (err) => console.error('Error updating exposure:', err)
      });
    } else {
      this.atlasApi.createExposure(data).subscribe({
        next: () => {
          this.showCreateModal = false;
          this.exposureForm.reset({ exposure_type: 'payable', currency: 'USD' });
          this.loadExposures();
          this.loadSummary();
        },
        error: (err) => console.error('Error creating exposure:', err)
      });
    }
  }

  closeModal(event: Event) {
    if (event.target === event.currentTarget) {
      this.showCreateModal = false;
      this.showUploadModal = false;
      this.editingExposure = null;
      this.uploadResult = null;
    }
  }

  onDragOver(event: DragEvent) {
    event.preventDefault();
    this.isDragOver = true;
  }

  onDragLeave(event: DragEvent) {
    event.preventDefault();
    this.isDragOver = false;
  }

  onDrop(event: DragEvent) {
    event.preventDefault();
    this.isDragOver = false;
    const files = event.dataTransfer?.files;
    if (files && files.length > 0) {
      this.selectedFile = files[0];
    }
  }

  onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.selectedFile = input.files[0];
    }
  }

  uploadFile() {
    if (!this.selectedFile) return;

    this.uploading = true;
    this.atlasApi.uploadExposures(this.selectedFile).subscribe({
      next: (result) => {
        this.uploadResult = result;
        this.uploading = false;
        this.selectedFile = null;
        this.loadExposures();
        this.loadSummary();
      },
      error: (err) => {
        console.error('Error uploading file:', err);
        this.uploading = false;
      }
    });
  }
}
