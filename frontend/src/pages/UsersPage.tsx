import React, { useEffect, useState } from 'react';
import { Box, Typography, Button, Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions, Snackbar, Alert, TextField } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import SearchIcon from '@mui/icons-material/Search';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
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
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState<'user_id' | 'username' | 'created_at'>('user_id');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');

  const {
    users,
    isLoading,
    fetchUsers,
    createUser,
    updateUser,
    deleteUser,
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

  const handleSort = (column: 'user_id' | 'username' | 'created_at') => {
    if (sortBy === column) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(column);
      setSortOrder('asc');
    }
  };

  const filteredUsers = users.filter(user => {
    const search = searchTerm.toLowerCase();
    const usernameMatch = user.username.toLowerCase().includes(search);
    const rolesMatch = user.roles?.some(role => role.toLowerCase().includes(search));
    return usernameMatch || rolesMatch;
  });

  const sortedUsers = [...filteredUsers].sort((a, b) => {
    let aValue: any = a[sortBy];
    let bValue: any = b[sortBy];

    if (sortBy === 'created_at') {
      aValue = new Date(aValue).getTime();
      bValue = new Date(bValue).getTime();
    }

    if (aValue < bValue) return sortOrder === 'asc' ? -1 : 1;
    if (aValue > bValue) return sortOrder === 'asc' ? 1 : -1;
    return 0;
  });

  return (
    <Layout>
      <Box sx={{ padding: 4 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3 }}>
          <Typography variant="h4">User Management</Typography>
          <Button variant="contained" startIcon={<AddIcon />} onClick={handleCreate}>Create User</Button>
        </Box>

        <TextField
          placeholder="Search by username or role..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          fullWidth
          sx={{ marginBottom: 3 }}
          InputProps={{
            startAdornment: <SearchIcon sx={{ color: '#999', marginRight: 1 }} />
          }}
        />

        <UserTable users={sortedUsers} currentUser={currentUser} onEdit={handleEdit} onDelete={handleDeleteClick} isLoading={isLoading} sortBy={sortBy} sortOrder={sortOrder} onSort={handleSort} />

        <UserFormDialog open={formOpen} user={selectedUser} onClose={handleFormClose} onSubmit={handleFormSubmit} />

        <Dialog open={deleteDialogOpen} onClose={handleDeleteCancel}>
          <DialogTitle>Confirm Delete</DialogTitle>
          <DialogContent>
            <DialogContentText>Are you sure you want to delete this user?</DialogContentText>

            {userToDelete !== null && users.find(u => u.user_id === userToDelete) && (
              <Box sx={{ marginTop: 2, padding: 2, background: '#FFF3E0', borderRadius: 1, border: '1px solid #FFB74D' }}>
                <Typography variant="body2" sx={{ fontWeight: 600, marginBottom: 1 }}>User Details:</Typography>
                <Typography variant="body2">Username: <strong>{users.find(u => u.user_id === userToDelete)?.username}</strong></Typography>
                <Typography variant="body2">Roles: <strong>{users.find(u => u.user_id === userToDelete)?.roles?.join(', ') || 'None'}</strong></Typography>
              </Box>
            )}

            <Typography variant="body2" sx={{ marginTop: 2, color: '#d32f2f' }}>
              This action cannot be undone.
            </Typography>
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
