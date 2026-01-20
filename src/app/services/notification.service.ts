/**
 * Notification Service - Alertas visuales en la UI
 */
import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';

export interface Notification {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info' | 'signal';
  title: string;
  message: string;
  timestamp: Date;
  read: boolean;
  data?: any;
}

@Injectable({
  providedIn: 'root'
})
export class NotificationService {
  private notifications: Notification[] = [];
  private notificationsSubject = new BehaviorSubject<Notification[]>([]);
  private unreadCountSubject = new BehaviorSubject<number>(0);

  notifications$ = this.notificationsSubject.asObservable();
  unreadCount$ = this.unreadCountSubject.asObservable();

  constructor() {
    // Cargar notificaciones guardadas
    const saved = localStorage.getItem('notifications');
    if (saved) {
      this.notifications = JSON.parse(saved);
      this.updateSubjects();
    }
  }

  private generateId(): string {
    return Math.random().toString(36).substring(2, 15);
  }

  private updateSubjects(): void {
    this.notificationsSubject.next([...this.notifications]);
    this.unreadCountSubject.next(this.notifications.filter(n => !n.read).length);
    localStorage.setItem('notifications', JSON.stringify(this.notifications));
  }

  show(type: Notification['type'], title: string, message: string, data?: any): void {
    const notification: Notification = {
      id: this.generateId(),
      type,
      title,
      message,
      timestamp: new Date(),
      read: false,
      data
    };

    this.notifications.unshift(notification);

    // Mantener solo las ultimas 50 notificaciones
    if (this.notifications.length > 50) {
      this.notifications = this.notifications.slice(0, 50);
    }

    this.updateSubjects();

    // Auto-ocultar notificaciones de exito despues de 5 segundos
    if (type === 'success' || type === 'info') {
      setTimeout(() => this.markAsRead(notification.id), 5000);
    }
  }

  success(title: string, message: string): void {
    this.show('success', title, message);
  }

  error(title: string, message: string): void {
    this.show('error', title, message);
  }

  warning(title: string, message: string): void {
    this.show('warning', title, message);
  }

  info(title: string, message: string): void {
    this.show('info', title, message);
  }

  tradingSignal(action: string, confidence: number, expectedReturn: number, data: any): void {
    const emoji = action === 'BUY_USD' ? '🟢' : action === 'SELL_USD' ? '🔴' : '⚪';
    this.show(
      'signal',
      `${emoji} Senal: ${action}`,
      `Confianza: ${(confidence * 100).toFixed(1)}% | Retorno esperado: ${(expectedReturn * 100).toFixed(2)}%`,
      data
    );
  }

  markAsRead(id: string): void {
    const notification = this.notifications.find(n => n.id === id);
    if (notification) {
      notification.read = true;
      this.updateSubjects();
    }
  }

  markAllAsRead(): void {
    this.notifications.forEach(n => n.read = true);
    this.updateSubjects();
  }

  remove(id: string): void {
    this.notifications = this.notifications.filter(n => n.id !== id);
    this.updateSubjects();
  }

  clearAll(): void {
    this.notifications = [];
    this.updateSubjects();
  }

  getRecent(count: number = 10): Notification[] {
    return this.notifications.slice(0, count);
  }
}
