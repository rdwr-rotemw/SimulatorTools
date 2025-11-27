import React from 'react';
import { Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, IconButton, Chip, CircularProgress, Typography, Box } from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import { User } from '../../types/user.types';

interface UserTableProps {
  users: User[];
  currentUser: User | null;
  onEdit: (user: User) => void;
  onDelete: (userId: number) => void;
  isLoading: boolean;
}

export const UserTable: React.FC<UserTableProps> = ({ users, currentUser, onEdit, onDelete, isLoading }) => {
  // Safety: ensure we always have an array to map over
  const safeUsers = users || [];

  if (isLoading) {
    return (
      <Box sx={{ minHeight: '200px', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
        <CircularProgress />
      </Box>
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
    <TableContainer component={Paper}>
      <Table stickyHeader>
        <TableHead>
          <TableRow>
            <TableCell>User ID</TableCell>
            <TableCell>Username</TableCell>
            <TableCell>Roles</TableCell>
            <TableCell>Active</TableCell>
            <TableCell>Created At</TableCell>
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
                      <IconButton aria-label="edit" color="primary" onClick={() => onEdit(user)} disabled={!canModify}>
                        <EditIcon />
                      </IconButton>
                      <IconButton aria-label="delete" color="error" onClick={() => onDelete(user.user_id)} disabled={!canModify}>
                        <DeleteIcon />
                      </IconButton>
                    </>
                  );
                })()}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
};
