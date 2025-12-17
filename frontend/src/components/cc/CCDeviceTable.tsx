import React from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Chip,
  CircularProgress,
  Typography,
  Box,
  Tooltip,
  Skeleton,
  Fade,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import { CCDevice } from '../../types/cc.types';

interface CCDeviceTableProps {
  devices: CCDevice[];
  onDelete: (device_id: string) => void;
  isLoading: boolean;
  sortBy: 'management_ip' | 'name' | 'device_type' | 'status';
  sortOrder: 'asc' | 'desc';
  onSort: (column: 'management_ip' | 'name' | 'device_type' | 'status') => void;
}

const getStatusTooltip = (status: string | undefined): string => {
  if (!status) return 'Status unknown';
  switch (status.toUpperCase()) {
    case 'OK':
    case 'ONLINE':
      return 'Device is connected and operational';
    case 'OFFLINE':
      return 'Device is not responding';
    case 'ERROR':
      return 'Device encountered an error';
    case 'PENDING':
      return 'Device connection is being established';
    default:
      return status;
  }
};

export const CCDeviceTable: React.FC<CCDeviceTableProps> = ({ devices, onDelete, isLoading, sortBy, sortOrder, onSort }) => {
  if (isLoading) {
    return (
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell
                onClick={() => onSort('management_ip')}
                sx={{ cursor: 'pointer', userSelect: 'none', '&:hover': { background: '#f5f5f5' } }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  Management IP
                  {sortBy === 'management_ip' && (sortOrder === 'asc' ? <ArrowUpwardIcon fontSize="small" /> : <ArrowDownwardIcon fontSize="small" />)}
                </Box>
              </TableCell>
              <TableCell
                onClick={() => onSort('name')}
                sx={{ cursor: 'pointer', userSelect: 'none', '&:hover': { background: '#f5f5f5' } }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  Name
                  {sortBy === 'name' && (sortOrder === 'asc' ? <ArrowUpwardIcon fontSize="small" /> : <ArrowDownwardIcon fontSize="small" />)}
                </Box>
              </TableCell>
              <TableCell>Device ID</TableCell>
              <TableCell
                onClick={() => onSort('device_type')}
                sx={{ cursor: 'pointer', userSelect: 'none', '&:hover': { background: '#f5f5f5' } }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  Device Type
                  {sortBy === 'device_type' && (sortOrder === 'asc' ? <ArrowUpwardIcon fontSize="small" /> : <ArrowDownwardIcon fontSize="small" />)}
                </Box>
              </TableCell>
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
                <TableCell><Skeleton variant="text" width={200} /></TableCell>
                <TableCell><Skeleton variant="text" width={90} /></TableCell>
                <TableCell><Skeleton variant="rectangular" width={80} height={24} sx={{ borderRadius: '12px' }} /></TableCell>
                <TableCell>
                  <Skeleton variant="circular" width={24} height={24} sx={{ display: 'inline-block' }} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    );
  }

  if (!devices || devices.length === 0) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" height={200}>
        <Typography>No devices found. Click 'Add Device' to get started.</Typography>
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
                onClick={() => onSort('management_ip')}
                sx={{ cursor: 'pointer', userSelect: 'none', '&:hover': { background: '#f5f5f5' } }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  Management IP
                  {sortBy === 'management_ip' && (sortOrder === 'asc' ? <ArrowUpwardIcon fontSize="small" /> : <ArrowDownwardIcon fontSize="small" />)}
                </Box>
              </TableCell>
              <TableCell
                onClick={() => onSort('name')}
                sx={{ cursor: 'pointer', userSelect: 'none', '&:hover': { background: '#f5f5f5' } }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  Name
                  {sortBy === 'name' && (sortOrder === 'asc' ? <ArrowUpwardIcon fontSize="small" /> : <ArrowDownwardIcon fontSize="small" />)}
                </Box>
              </TableCell>
              <TableCell>Device ID</TableCell>
              <TableCell
                onClick={() => onSort('device_type')}
                sx={{ cursor: 'pointer', userSelect: 'none', '&:hover': { background: '#f5f5f5' } }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  Device Type
                  {sortBy === 'device_type' && (sortOrder === 'asc' ? <ArrowUpwardIcon fontSize="small" /> : <ArrowDownwardIcon fontSize="small" />)}
                </Box>
              </TableCell>
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
            {devices.map((device) => {
              const status = device?.status ?? '';
              const isOk = status.toLowerCase() === 'ok' || status.toLowerCase() === 'online';

              return (
                <TableRow key={device.management_ip}>
                  <TableCell>{device.management_ip}</TableCell>
                  <TableCell>{device.name ?? '-'}</TableCell>
                  <TableCell>{device.device_id ?? '-'}</TableCell>
                  <TableCell>{device.device_type ?? '-'}</TableCell>
                  <TableCell>
                    <Tooltip title={getStatusTooltip(status)} arrow>
                      <Chip label={status || '-'} color={isOk ? 'success' : 'default'} size="small" />
                    </Tooltip>
                  </TableCell>
                  <TableCell>
                    <IconButton aria-label="delete" color="error" onClick={() => onDelete(device.device_id || device.management_ip)}>
                      <DeleteIcon />
                    </IconButton>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
    </Fade>
  );
};
