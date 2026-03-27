"use client";

import { Clock, CheckCircle2, XCircle, AlertTriangle, Play, Users } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { QueueMetrics } from "@/types";

interface QueueStatusProps {
  metrics: QueueMetrics;
}

export function QueueStatus({ metrics }: QueueStatusProps) {
  const totalJobs = metrics.pending_jobs + metrics.processing_jobs + metrics.completed_jobs + metrics.failed_jobs;
  const successRate = totalJobs > 0 ? ((metrics.completed_jobs / totalJobs) * 100) : 0;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-lg flex items-center gap-2">
          <Play className="h-5 w-5" />
          Cola de Jobs
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Status Bars */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-1.5 text-yellow-600">
                <Clock className="h-4 w-4" />
                Pendientes
              </span>
              <span className="font-bold">{metrics.pending_jobs}</span>
            </div>
            <Progress value={Math.min((metrics.pending_jobs / 100) * 100, 100)} className="h-2 bg-yellow-100" />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-1.5 text-blue-600">
                <Play className="h-4 w-4" />
                Procesando
              </span>
              <span className="font-bold">{metrics.processing_jobs}</span>
            </div>
            <Progress value={Math.min((metrics.processing_jobs / 20) * 100, 100)} className="h-2 bg-blue-100" />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-1.5 text-green-600">
                <CheckCircle2 className="h-4 w-4" />
                Completados
              </span>
              <span className="font-bold">{metrics.completed_jobs}</span>
            </div>
            <Progress value={successRate} className="h-2 bg-green-100" />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-1.5 text-red-600">
                <XCircle className="h-4 w-4" />
                Fallidos
              </span>
              <span className="font-bold">{metrics.failed_jobs}</span>
            </div>
            <Progress
              value={totalJobs > 0 ? (metrics.failed_jobs / totalJobs) * 100 : 0}
              className="h-2 bg-red-100"
            />
          </div>
        </div>

        {/* Dead Letter Queue Warning */}
        {metrics.dead_letter_jobs > 0 && (
          <div className="flex items-center gap-2 p-3 bg-orange-50 border border-orange-200 rounded-lg">
            <AlertTriangle className="h-5 w-5 text-orange-600" />
            <div className="flex-1">
              <span className="text-sm font-medium text-orange-800">
                {metrics.dead_letter_jobs} jobs en Dead Letter Queue
              </span>
              <p className="text-xs text-orange-600">Requieren revision manual</p>
            </div>
          </div>
        )}

        {/* Stats Row */}
        <div className="grid grid-cols-3 gap-4 pt-2 border-t">
          <div className="text-center">
            <div className="flex items-center justify-center gap-1 text-muted-foreground mb-1">
              <Users className="h-4 w-4" />
              <span className="text-xs">Workers</span>
            </div>
            <span className="text-xl font-bold">{metrics.active_workers}</span>
          </div>
          <div className="text-center">
            <div className="text-xs text-muted-foreground mb-1">Tasa Error</div>
            <span className={`text-xl font-bold ${metrics.error_rate > 0.05 ? 'text-red-600' : 'text-green-600'}`}>
              {(metrics.error_rate * 100).toFixed(1)}%
            </span>
          </div>
          <div className="text-center">
            <div className="text-xs text-muted-foreground mb-1">Tiempo Proc.</div>
            <span className="text-xl font-bold">
              {metrics.avg_processing_time_seconds.toFixed(1)}s
            </span>
          </div>
        </div>

        {/* Jobs by Type */}
        {Object.keys(metrics.jobs_by_type).length > 0 && (
          <div className="pt-2 border-t">
            <p className="text-xs text-muted-foreground mb-2">Jobs por Tipo</p>
            <div className="flex flex-wrap gap-2">
              {Object.entries(metrics.jobs_by_type).map(([type, count]) => (
                <div key={type} className="px-2 py-1 bg-gray-100 rounded text-xs">
                  <span className="text-gray-600">{type}:</span>
                  <span className="font-medium ml-1">{count}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
