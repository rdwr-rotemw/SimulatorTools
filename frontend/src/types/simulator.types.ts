export interface Simulator {
  ip_address: string;
  type: string;
  version: string;
  map: string;
  status: string;
  created_at: string;
}

export interface SimulatorCreate {
  ip_address: string;
  type: string;
  version: string;
  map: string;
  status: string;
}

export interface SimulatorUpdate {
  type: string;
  version: string;
  map: string;
  status: string;
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

