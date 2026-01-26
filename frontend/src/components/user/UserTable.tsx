import React from 'react';
import { Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, IconButton, Chip, CircularProgress, Typography, Box, Tooltip, Skeleton, Fade } from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import { User } from '../../types/user.types';

interface UserTableProps {
  users: User[];
  currentUser: User | null;
  onEdit: (user: User) => void;
  onDelete: (userId: number) => void;
  isLoading: boolean;
  sortBy: 'user_id' | 'username' | 'created_at';
  sortOrder: 'asc' | 'desc';
  onSort: (column: 'user_id' | 'username' | 'created_at') => void;
}

export const UserTable: React.FC<UserTableProps> = ({ users, currentUser, onEdit, onDelete, isLoading, sortBy, sortOrder, onSort }) => {
  // Safety: ensure we always have an array to map over
  const safeUsers = users || [];

  if (isLoading) {
    return (
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell
                onClick={() => onSort('user_id')}
                sx={{ cursor: 'pointer', userSelect: 'none', '&:hover': { background: '#f5f5f5' } }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  User ID
                  {sortBy === 'user_id' && (sortOrder === 'asc' ? <ArrowUpwardIcon fontSize="small" /> : <ArrowDownwardIcon fontSize="small" />)}
                </Box>
              </TableCell>
              <TableCell
                onClick={() => onSort('username')}
                sx={{ cursor: 'pointer', userSelect: 'none', '&:hover': { background: '#f5f5f5' } }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  Username
                  {sortBy === 'username' && (sortOrder === 'asc' ? <ArrowUpwardIcon fontSize="small" /> : <ArrowDownwardIcon fontSize="small" />)}
                </Box>
              </TableCell>
              <TableCell>Roles</TableCell>
              <TableCell>Workspace</TableCell>
              <TableCell>Active</TableCell>
              <TableCell
                onClick={() => onSort('created_at')}
                sx={{ cursor: 'pointer', userSelect: 'none', '&:hover': { background: '#f5f5f5' } }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  Created At
                  {sortBy === 'created_at' && (sortOrder === 'asc' ? <ArrowUpwardIcon fontSize="small" /> : <ArrowDownwardIcon fontSize="small" />)}
                </Box>
              </TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {[1, 2, 3, 4, 5].map((n) => (
              <TableRow key={n}>
                <TableCell><Skeleton variant="text" width={30} /></TableCell>
                <TableCell><Skeleton variant="text" width={120} /></TableCell>
                <TableCell><Skeleton variant="rectangular" width={100} height={24} sx={{ borderRadius: '12px' }} /></TableCell>
                <TableCell><Skeleton variant="rectangular" width={100} height={24} sx={{ borderRadius: '12px' }} /></TableCell>
                <TableCell><Skeleton variant="rectangular" width={80} height={24} sx={{ borderRadius: '12px' }} /></TableCell>  {/* Workspace skeleton */}
                <TableCell><Skeleton variant="rectangular" width={70} height={24} sx={{ borderRadius: '12px' }} /></TableCell>
                <TableCell><Skeleton variant="text" width={100} /></TableCell>
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

  if (!isLoading && (safeUsers.length === 0)) {
    return (
      <Box sx={{ minHeight: '200px', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
        <Typography>No users found</Typography>
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
                onClick={() => onSort('user_id')}
                sx={{ cursor: 'pointer', userSelect: 'none', '&:hover': { background: '#f5f5f5' } }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  User ID
                  {sortBy === 'user_id' && (sortOrder === 'asc' ? <ArrowUpwardIcon fontSize="small" /> : <ArrowDownwardIcon fontSize="small" />)}
                </Box>
              </TableCell>
              <TableCell
                onClick={() => onSort('username')}
                sx={{ cursor: 'pointer', userSelect: 'none', '&:hover': { background: '#f5f5f5' } }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  Username
                  {sortBy === 'username' && (sortOrder === 'asc' ? <ArrowUpwardIcon fontSize="small" /> : <ArrowDownwardIcon fontSize="small" />)}
                </Box>
              </TableCell>
              <TableCell>Roles</TableCell>
              <TableCell>Workspace</TableCell>
              <TableCell>Active</TableCell>
              <TableCell
                onClick={() => onSort('created_at')}
                sx={{ cursor: 'pointer', userSelect: 'none', '&:hover': { background: '#f5f5f5' } }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  Created At
                  {sortBy === 'created_at' && (sortOrder === 'asc' ? <ArrowUpwardIcon fontSize="small" /> : <ArrowDownwardIcon fontSize="small" />)}
                </Box>
              </TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {safeUsers.map((user) => (
              <TableRow key={user.user_id} hover>
                <TableCell>{user.user_id}</TableCell>
                <TableCell>{user.username}</TableCell>
                <TableCell>
                  {(user.roles || []).map((role, idx) => (
                    <Chip key={`${user.user_id}-role-${idx}`} label={role} size="small" color="primary" sx={{ mr: 0.5 }} />
                  ))}
                </TableCell>
                <TableCell>
                  <Chip
                    label={user.workspace || 'Not assigned'}
                    size="small"
                    color={user.workspace === '*' ? 'secondary' : 'default'}
                    sx={{ fontFamily: 'monospace' }}
                  />
                </TableCell>
                <TableCell>
                  <Chip label={user.is_active ? 'Active' : 'Inactive'} color={user.is_active ? 'success' : 'default'} size="small" />
                </TableCell>
                <TableCell>{new Date(user.created_at).toLocaleDateString()}</TableCell>
                <TableCell>
                  {(() => {
                    const isSuperAdmin = currentUser?.username === 'admin';
                    const isTargetAdmin = (user.roles || []).includes('admin');
                    const canModify = !isTargetAdmin || isSuperAdmin;
                    return (
                      <>
                        <Tooltip title={!canModify ? "Only super admin can modify admin users" : "Edit user"} arrow>
                          <span>
                            <IconButton onClick={() => onEdit(user)} color="primary" disabled={!canModify}>
                              <EditIcon />
                            </IconButton>
                          </span>
                        </Tooltip>

                        <Tooltip title={!canModify ? "Only super admin can delete admin users" : "Delete user"} arrow>
                          <span>
                            <IconButton onClick={() => onDelete(user.user_id)} color="error" disabled={!canModify}>
                              <DeleteIcon />
                            </IconButton>
                          </span>
                        </Tooltip>
                      </>
                    );
                  })()}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Fade>
  );
};
