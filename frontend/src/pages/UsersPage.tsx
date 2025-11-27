import React, { useEffect, useState } from 'react';
import { Box, Typography, Button, Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions, Snackbar, Alert } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import Layout from '../components/common/Layout';
import { UserTable } from '../components/user/UserTable';
import { UserFormDialog } from '../components/user/UserFormDialog';
import { useAuthStore } from '../store/authStore';
import useUserStore from '../store/userStore';
import { User, UserCreate, UserUpdate } from '../types/user.types';

interface SnackbarState {
  open: boolean;
  message: string;
  severity: 'success' | 'error';
}

export const UsersPage: React.FC = () => {
  const [formOpen, setFormOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [userToDelete, setUserToDelete] = useState<number | null>(null);
  const [snackbar, setSnackbar] = useState<SnackbarState>({ open: false, message: '', severity: 'success' });

  const {
    users,
    isLoading,
    error,
    fetchUsers,
    createUser,
    updateUser,
    deleteUser,
    clearError,
  } = useUserStore();

  const currentUser = useAuthStore(state => state.user);

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleCreate = () => {
    setSelectedUser(null);
    setFormOpen(true);
  };

  const handleEdit = (user: User) => {
    setSelectedUser(user);
    setFormOpen(true);
  };

  const handleDeleteClick = (userId: number) => {
    setUserToDelete(userId);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (userToDelete !== null) {
      try {
        await deleteUser(userToDelete);
        setDeleteDialogOpen(false);
        setUserToDelete(null);
        setSnackbar({ open: true, message: 'User deleted successfully', severity: 'success' });
      } catch (error: any) {
        // Close dialog and clear selection, then show backend-provided error if available
        setDeleteDialogOpen(false);
        setUserToDelete(null);
        const message = error?.response?.data?.detail || error?.message || 'Failed to delete user';
        setSnackbar({ open: true, message, severity: 'error' });
      }
    }
  };

  const handleFormSubmit = async (data: UserCreate | UserUpdate) => {
    if (selectedUser) {
      await updateUser(selectedUser.user_id, data as UserUpdate);
    } else {
      await createUser(data as UserCreate);
    }
    setFormOpen(false);
    setSelectedUser(null);
    setSnackbar({ open: true, message: 'User saved successfully', severity: 'success' });
    // Let errors bubble up to the dialog - it will handle them
  };

  const handleFormClose = () => {
    setFormOpen(false);
    setSelectedUser(null);
  };

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false);
    setUserToDelete(null);
  };

  const handleSnackbarClose = (_?: any, reason?: string) => {
    if (reason === 'clickaway') return;
    setSnackbar((s) => ({ ...s, open: false }));
  };

  return (
    <Layout>
      <Box sx={{ padding: 4 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3 }}>
          <Typography variant="h4">User Management</Typography>
          <Button variant="contained" startIcon={<AddIcon />} onClick={handleCreate}>Create User</Button>
        </Box>

        <UserTable users={users} currentUser={currentUser} onEdit={handleEdit} onDelete={handleDeleteClick} isLoading={isLoading} />

        <UserFormDialog open={formOpen} user={selectedUser} onClose={handleFormClose} onSubmit={handleFormSubmit} />

        <Dialog open={deleteDialogOpen} onClose={handleDeleteCancel}>
          <DialogTitle>Confirm Delete</DialogTitle>
          <DialogContent>
            <DialogContentText>Are you sure you want to delete this user?</DialogContentText>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleDeleteCancel}>Cancel</Button>
            <Button onClick={handleDeleteConfirm} color="error" variant="contained">Delete</Button>
          </DialogActions>
        </Dialog>

        <Snackbar open={snackbar.open} autoHideDuration={6000} onClose={handleSnackbarClose}>
          <Alert onClose={handleSnackbarClose} severity={snackbar.severity} sx={{ width: '100%' }}>
            {snackbar.message}
          </Alert>
        </Snackbar>
      </Box>
    </Layout>
  );
};

export default UsersPage;
