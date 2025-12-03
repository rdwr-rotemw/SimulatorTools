import React from 'react';
import { Box, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, IconButton, Chip, Typography, Tooltip, Skeleton, Fade } from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import { Simulator } from '../../types/simulator.types';

interface SimulatorTableProps {
  simulators: Simulator[];
  onEdit: (simulator: Simulator) => void;
  onDelete: (ip: string) => void;
  isLoading: boolean;
  sortBy: 'ip_address' | 'type' | 'version' | 'status';
  sortOrder: 'asc' | 'desc';
  onSort: (column: 'ip_address' | 'type' | 'version' | 'status') => void;
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

const getStatusTooltip = (status: string): string => {
  switch ((status || '').toUpperCase()) {
    case 'OK':
      return 'Simulator is running and healthy';
    case 'LOADING':
      return 'Simulator is starting up';
    case 'FAILED':
      return 'Simulator encountered an error';
    case 'STOPPED':
      return 'Simulator is not running';
    case 'UNKNOWN':
      return 'Status information unavailable';
    default:
      return status || 'Unknown';
  }
};

export const SimulatorTable: React.FC<SimulatorTableProps> = ({ simulators, onEdit, onDelete, isLoading, sortBy, sortOrder, onSort }) => {
  if (isLoading) {
    return (
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell
                onClick={() => onSort('ip_address')}
                sx={{ cursor: 'pointer', userSelect: 'none', '&:hover': { background: '#f5f5f5' } }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  IP Address
                  {sortBy === 'ip_address' && (sortOrder === 'asc' ? <ArrowUpwardIcon fontSize="small" /> : <ArrowDownwardIcon fontSize="small" />)}
                </Box>
              </TableCell>
              <TableCell
                onClick={() => onSort('type')}
                sx={{ cursor: 'pointer', userSelect: 'none', '&:hover': { background: '#f5f5f5' } }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  Type
                  {sortBy === 'type' && (sortOrder === 'asc' ? <ArrowUpwardIcon fontSize="small" /> : <ArrowDownwardIcon fontSize="small" />)}
                </Box>
              </TableCell>
              <TableCell
                onClick={() => onSort('version')}
                sx={{ cursor: 'pointer', userSelect: 'none', '&:hover': { background: '#f5f5f5' } }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  Version
                  {sortBy === 'version' && (sortOrder === 'asc' ? <ArrowUpwardIcon fontSize="small" /> : <ArrowDownwardIcon fontSize="small" />)}
                </Box>
              </TableCell>
              <TableCell>Map</TableCell>
              <TableCell
                onClick={() => onSort('status')}
                sx={{ cursor: 'pointer', userSelect: 'none', '&:hover': { background: '#f5f5f5' } }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  Status
                  {sortBy === 'status' && (sortOrder === 'asc' ? <ArrowUpwardIcon fontSize="small" /> : <ArrowDownwardIcon fontSize="small" />)}
                </Box>
              </TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {[1, 2, 3, 4, 5].map((n) => (
              <TableRow key={n}>
                <TableCell><Skeleton variant="text" width={120} /></TableCell>
                <TableCell><Skeleton variant="text" width={100} /></TableCell>
                <TableCell><Skeleton variant="text" width={80} /></TableCell>
                <TableCell><Skeleton variant="text" width={90} /></TableCell>
                <TableCell><Skeleton variant="rectangular" width={80} height={24} sx={{ borderRadius: '12px' }} /></TableCell>
                <TableCell>
                  <Skeleton variant="circular" width={24} height={24} sx={{ display: 'inline-block', marginRight: 1 }} />
                  <Skeleton variant="circular" width={24} height={24} sx={{ display: 'inline-block' }} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
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
    <Fade in={true} timeout={600}>
      <TableContainer component={Paper}>
        <Table stickyHeader>
          <TableHead>
            <TableRow>
              <TableCell
                onClick={() => onSort('ip_address')}
                sx={{ cursor: 'pointer', userSelect: 'none', '&:hover': { background: '#f5f5f5' } }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  IP Address
                  {sortBy === 'ip_address' && (sortOrder === 'asc' ? <ArrowUpwardIcon fontSize="small" /> : <ArrowDownwardIcon fontSize="small" />)}
                </Box>
              </TableCell>
              <TableCell
                onClick={() => onSort('type')}
                sx={{ cursor: 'pointer', userSelect: 'none', '&:hover': { background: '#f5f5f5' } }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  Type
                  {sortBy === 'type' && (sortOrder === 'asc' ? <ArrowUpwardIcon fontSize="small" /> : <ArrowDownwardIcon fontSize="small" />)}
                </Box>
              </TableCell>
              <TableCell
                onClick={() => onSort('version')}
                sx={{ cursor: 'pointer', userSelect: 'none', '&:hover': { background: '#f5f5f5' } }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  Version
                  {sortBy === 'version' && (sortOrder === 'asc' ? <ArrowUpwardIcon fontSize="small" /> : <ArrowDownwardIcon fontSize="small" />)}
                </Box>
              </TableCell>
              <TableCell>Map</TableCell>
              <TableCell
                onClick={() => onSort('status')}
                sx={{ cursor: 'pointer', userSelect: 'none', '&:hover': { background: '#f5f5f5' } }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  Status
                  {sortBy === 'status' && (sortOrder === 'asc' ? <ArrowUpwardIcon fontSize="small" /> : <ArrowDownwardIcon fontSize="small" />)}
                </Box>
              </TableCell>
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
                  <Tooltip title={getStatusTooltip(sim.status)} arrow>
                    <Chip label={sim.status} color={getStatusColor(sim.status)} size="small" />
                  </Tooltip>
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
    </Fade>
  );
};
