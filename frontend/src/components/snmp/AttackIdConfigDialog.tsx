import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Alert,
  Tabs,
  Tab,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TextField,
  IconButton,
  Box,
  Typography
} from '@mui/material';
import CasinoIcon from '@mui/icons-material/Casino';

export interface SNMPTrap {
  attackId?: string;
  [key: string]: any;
}

interface AttackIdConfigDialogProps {
  open: boolean;
  onClose: () => void;
  simulators: string[];
  traps: SNMPTrap[];
  onConfirm: (attackIdConfig: Record<string, string[]>) => void;
}

const AttackIdConfigDialog: React.FC<AttackIdConfigDialogProps> = ({
  open,
  onClose,
  simulators,
  traps,
  onConfirm
}) => {
  const [currentTab, setCurrentTab] = useState(0);
  const [attackIds, setAttackIds] = useState<Record<string, string[]>>({});

  // Generate a random attack-ID
  const generateAttackId = (): string => {
    const prefix = Math.floor(Math.random() * 9000) + 100; // 100-9999
    const suffix = Math.floor(Math.random() * 9000000000) + 1000000000; // 10 digits
    return `${prefix}-${suffix}`;
  };

  // Initialize/reset state when dialog opens or props change
  useEffect(() => {
    if (open && simulators.length > 0 && traps.length > 0) {
      const initial: Record<string, string[]> = {};

      // First simulator: keep original attack-IDs from traps
      initial[simulators[0]] = traps.map(trap => trap.attackId || '');

      // Other simulators: randomize while maintaining grouping
      if (simulators.length > 1) {
        const originalIds = traps.map(trap => trap.attackId || '');
        simulators.slice(1).forEach(ip => {
          const idMapping: Record<string, string> = {};
          initial[ip] = originalIds.map(origId => {
            if (!idMapping[origId]) {
              idMapping[origId] = generateAttackId();
            }
            return idMapping[origId];
          });
        });
      }

      setAttackIds(initial);
      setCurrentTab(0); // Reset to first tab
    }
  }, [open, simulators, traps]);

  const currentSimulatorIp = simulators[currentTab];

  // Handle attack-ID change for a specific trap
  const handleAttackIdChange = (simulatorIp: string, trapIndex: number, newValue: string) => {
    setAttackIds(prev => ({
      ...prev,
      [simulatorIp]: prev[simulatorIp].map((id, idx) =>
        idx === trapIndex ? newValue : id
      )
    }));
  };

  // Randomize a single trap's attack-ID (and all traps with same original ID)
  const randomizeSingle = (simulatorIp: string, trapIndex: number) => {
    const newAttackId = generateAttackId();
    const originalAttackId = traps[trapIndex].attackId;

    setAttackIds(prev => {
      const updated = { ...prev };

      // Find all traps with same original attack-ID and update them
      traps.forEach((trap, idx) => {
        if (trap.attackId === originalAttackId) {
          if (!updated[simulatorIp]) {
            updated[simulatorIp] = [...traps.map(t => t.attackId || '')];
          }
          updated[simulatorIp][idx] = newAttackId;
        }
      });

      return updated;
    });
  };

  // Randomize all attack-IDs for the current simulator
  const randomizeAllForSimulator = () => {
    const originalIds = traps.map(trap => trap.attackId || '');
    const idMapping: Record<string, string> = {};

    const newIds = originalIds.map(origId => {
      if (!idMapping[origId]) {
        idMapping[origId] = generateAttackId();
      }
      return idMapping[origId];
    });

    setAttackIds(prev => ({
      ...prev,
      [currentSimulatorIp]: newIds
    }));
  };

  // Randomize all simulators (except first one)
  const randomizeAllSimulators = () => {
    const originalIds = traps.map(trap => trap.attackId || '');

    setAttackIds(prev => {
      const newState = { ...prev };
      simulators.slice(1).forEach(ip => {
        const idMapping: Record<string, string> = {};
        newState[ip] = originalIds.map(origId => {
          if (!idMapping[origId]) {
            idMapping[origId] = generateAttackId();
          }
          return idMapping[origId];
        });
      });
      return newState;
    });
  };

  const handleConfirm = () => {
    onConfirm(attackIds);
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
    >
      <DialogTitle>
        ⚠️ Multiple Simulators Selected - Attack-ID Configuration Required
      </DialogTitle>

      <DialogContent>
        <Alert severity="info" sx={{ mb: 2 }}>
          CyberController requires unique attack-IDs per simulator.
          Configure attack-IDs for each simulator below.
          <br />
          <strong>Note:</strong> Traps with the same original attack-ID will share the same randomized value.
        </Alert>

        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Tabs
            value={currentTab}
            onChange={(e, newValue) => setCurrentTab(newValue)}
            variant="scrollable"
            scrollButtons="auto"
          >
            {simulators.map((ip, index) => (
              <Tab
                key={ip}
                label={`${ip}${index === 0 ? ' (Original)' : ''}`}
                value={index}
              />
            ))}
          </Tabs>
        </Box>

        <Box sx={{ mb: 2, display: 'flex', gap: 1 }}>
          {currentTab === 0 ? (
            // Original tab: only show "Randomize All Non-Original Simulators" button
            <Button
              onClick={randomizeAllSimulators}
              startIcon={<CasinoIcon />}
              variant="outlined"
              size="small"
              color="secondary"
            >
              Randomize All Non-Original Simulators
            </Button>
          ) : (
            // Other tabs: show both buttons
            <>
              <Button
                onClick={randomizeAllForSimulator}
                startIcon={<CasinoIcon />}
                variant="outlined"
                size="small"
              >
                Randomize All for {currentSimulatorIp}
              </Button>
              <Button
                onClick={randomizeAllSimulators}
                startIcon={<CasinoIcon />}
                variant="outlined"
                size="small"
                color="secondary"
              >
                Randomize All Non-Original Simulators
              </Button>
            </>
          )}
        </Box>

        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell><strong>Trap #</strong></TableCell>
              <TableCell><strong>Attack-ID</strong></TableCell>
              <TableCell align="center"><strong>Actions</strong></TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {traps.map((trap, index) => {
              return (
                <TableRow key={index}>
                  <TableCell>
                    <Typography variant="body2">
                      Trap {index + 1}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <TextField
                      value={attackIds[currentSimulatorIp]?.[index] || ''}
                      onChange={(e) => handleAttackIdChange(currentSimulatorIp, index, e.target.value)}
                      fullWidth
                      size="small"
                      placeholder="e.g., 333-1234567890"
                    />
                  </TableCell>
                  <TableCell align="center">
                    <IconButton
                      onClick={() => randomizeSingle(currentSimulatorIp, index)}
                      size="small"
                      title="Randomize this trap's attack-ID"
                    >
                      <CasinoIcon />
                    </IconButton>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>

        {traps.length === 0 && (
          <Alert severity="warning" sx={{ mt: 2 }}>
            No traps available to configure.
          </Alert>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          onClick={handleConfirm}
          variant="contained"
          disabled={traps.length === 0}
        >
          Send Traps
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default AttackIdConfigDialog;
