import React from 'react';
import { Box, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, IconButton, Chip, CircularProgress, Typography } from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import { Simulator } from '../../types/simulator.types';

interface SimulatorTableProps {
  simulators: Simulator[];
  onEdit: (simulator: Simulator) => void;
  onDelete: (ip: string) => void;
  isLoading: boolean;
}

const getStatusColor = (status: string): 'default' | 'success' | 'warning' | 'error' => {
  switch ((status || '').toUpperCase()) {
    case 'OK':
      return 'success';
    case 'LOADING':
      return 'warning';
    case 'FAILED':
      return 'error';
    case 'STOPPING':
      return 'warning';
    case 'SHUTDOWN':
    case 'DISABLED':
    default:
      return 'default';
  }
};

export const SimulatorTable: React.FC<SimulatorTableProps> = ({ simulators, onEdit, onDelete, isLoading }) => {
  if (isLoading) {
    return (
      <Box sx={{ minHeight: '200px', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!isLoading && (!simulators || simulators.length === 0)) {
    return (
      <Box sx={{ minHeight: '200px', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
        <Typography>No simulators found</Typography>
      </Box>
    );
  }

  return (
    <TableContainer component={Paper}>
      <Table stickyHeader>
        <TableHead>
          <TableRow>
            <TableCell>IP Address</TableCell>
            <TableCell>Type</TableCell>
            <TableCell>Version</TableCell>
            <TableCell>Map</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {simulators.map((sim) => (
            <TableRow key={sim.ip_address} hover>
              <TableCell>{sim.ip_address}</TableCell>
              <TableCell>{sim.type}</TableCell>
              <TableCell>{sim.version}</TableCell>
              <TableCell>{sim.map}</TableCell>
              <TableCell>
                <Chip label={sim.status} color={getStatusColor(sim.status)} size="small" />
              </TableCell>
              <TableCell>
                <IconButton aria-label="edit" color="primary" onClick={() => onEdit(sim)}>
                  <EditIcon />
                </IconButton>
                <IconButton aria-label="delete" color="error" onClick={() => onDelete(sim.ip_address)}>
                  <DeleteIcon />
                </IconButton>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
};

export default SimulatorTable;
