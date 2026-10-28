import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  adaptCurve,
  adaptElasticity,
  adaptFarePrediction,
  adaptPnl,
  adaptRivals,
  adaptSuggestion,
  adaptTotals,
  type RawCurve,
  type RawElasticity,
  type RawFarePrediction,
  type RawPnl,
  type RawRivals,
  type RawSuggestion,
  type RawTotals,
} from './adapters';
import { api, qs } from './client';
import type {
  Decision,
  DecisionIn,
  DeskFilters,
  DeskPage,
  DeskSummary,
  FarePredictInput,
  RouteInfo,
  Rules,
  RulesInput,
  Suggestion,
  User,
  Warning,
  WhatIf,
} from './types';

const MINUTE = 60_000;

export const useDeskSummary = (f: Pick<DeskFilters, 'window' | 'corridor_id'>) =>
  useQuery({
    queryKey: ['desk', 'summary', f],
    queryFn: () => api<DeskSummary>(`/desk/summary${qs({ window: f.window, corridor_id: f.corridor_id })}`),
    staleTime: MINUTE,
  });

export const useRoutes = () =>
  useQuery({
    queryKey: ['routes'],
    queryFn: () => api<{ items: RouteInfo[] }>('/routes'),
    staleTime: 5 * MINUTE,
  });

export const useUsers = () =>
  useQuery({ queryKey: ['users'], queryFn: () => api<{ items: User[] }>('/users'), staleTime: 5 * MINUTE });

export const useDeskServices = (f: DeskFilters) =>
  useQuery({
    queryKey: ['desk', 'services', f],
    queryFn: () =>
      api<DeskPage>(`/desk/services${qs({ window: f.window, corridor_id: f.corridor_id, page: f.page })}`),
    staleTime: MINUTE,
    placeholderData: (prev) => prev,
  });

export const useSuggestion = (id: string) =>
  useQuery({
    queryKey: ['suggestion', id],
    queryFn: async () => adaptSuggestion(await api<RawSuggestion>(`/services/${id}/suggestion`)),
    staleTime: MINUTE,
  });

export const useWhatIf = (id: string) =>
  useQuery({
    queryKey: ['whatif', id],
    queryFn: () => api<WhatIf>(`/services/${id}/whatif`),
    staleTime: MINUTE,
  });

export const usePnl = (id: string) =>
  useQuery({
    queryKey: ['pnl', id],
    queryFn: async () => adaptPnl(await api<RawPnl>(`/pnl/services/${id}`)),
    staleTime: MINUTE,
  });

export const useCurve = (id: string) =>
  useQuery({
    queryKey: ['curve', id],
    queryFn: async () => adaptCurve(await api<RawCurve>(`/forecast/services/${id}/curve`)),
    staleTime: MINUTE,
  });

interface ElasticityParams {
  route_id: string;
  slot?: string;
  dtg_band?: string;
  day_type?: string;
}
export const useElasticity = (p: ElasticityParams | null) =>
  useQuery({
    queryKey: ['elasticity', p],
    queryFn: async () => adaptElasticity(await api<RawElasticity>(`/pricing/elasticity${qs({ ...p })}`)),
    staleTime: 5 * MINUTE,
    enabled: p !== null,
  });

export const useRivals = (id: string) =>
  useQuery({
    queryKey: ['rivals', id],
    queryFn: async () => adaptRivals(await api<RawRivals>(`/rivals/services/${id}`)),
    staleTime: MINUTE,
  });

export const useTotals = (groupBy: string) =>
  useQuery({
    queryKey: ['totals', groupBy],
    queryFn: async () => adaptTotals(await api<RawTotals>(`/pnl/totals${qs({ group_by: groupBy })}`)),
    staleTime: MINUTE,
    retry: false,
  });

export const useWarnings = () =>
  useQuery({
    queryKey: ['warnings'],
    queryFn: () => api<{ items: Warning[] }>('/warnings'),
    staleTime: MINUTE,
  });

export const useDecisions = (serviceId: string) =>
  useQuery({
    queryKey: ['decisions', serviceId],
    queryFn: () => api<{ items: Decision[] }>(`/decisions${qs({ service_id: serviceId })}`),
    staleTime: 0,
  });

export const useRules = () =>
  useQuery({ queryKey: ['rules'], queryFn: () => api<Rules>('/rules'), staleTime: 5 * MINUTE });

export function useUpdateRules() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: RulesInput) => api<Rules>('/rules', { method: 'PUT', body: JSON.stringify(body) }),
    onSuccess: (rules) => {
      qc.setQueryData(['rules'], rules);
      void qc.invalidateQueries({ queryKey: ['suggestion'] });
      void qc.invalidateQueries({ queryKey: ['whatif'] });
    },
  });
}

export function useDecide(suggestion: Pick<Suggestion, 'suggestion_id' | 'service_id'>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: DecisionIn) =>
      api<Decision>(`/suggestions/${suggestion.suggestion_id}/decision`, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['suggestion', suggestion.service_id] });
      void qc.invalidateQueries({ queryKey: ['decisions', suggestion.service_id] });
      void qc.invalidateQueries({ queryKey: ['desk'] });
      void qc.invalidateQueries({ queryKey: ['warnings'] });
    },
  });
}

export function useFarePredict() {
  return useMutation({
    mutationFn: async (body: FarePredictInput) =>
      adaptFarePrediction(
        await api<RawFarePrediction>('/fare/predict', { method: 'POST', body: JSON.stringify(body) }),
      ),
  });
}
