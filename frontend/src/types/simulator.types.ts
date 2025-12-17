export interface Simulator {
  ip_address: string;
  map: string;
  template_id?: string;
  type?: string;
  version?: string;
  status?: string;
  created_at: string;
}

export interface SimulatorCreate {
  ip_address: string;
  map: string;
  template_id: string;
}

export interface SimulatorUpdate {
  map?: string;
  template_id?: string;
}

export interface SimulatorState {
  simulators: Simulator[];
  selectedSimulator: Simulator | null;
  isLoading: boolean;
  error: string | null;

  fetchSimulators: () => Promise<void>;
  fetchSimulator: (ip: string) => Promise<void>;
  createSimulator: (data: SimulatorCreate) => Promise<void>;
  updateSimulator: (ip: string, data: SimulatorUpdate) => Promise<void>;
  deleteSimulator: (ip: string) => Promise<void>;

  clearError: () => void;
}
