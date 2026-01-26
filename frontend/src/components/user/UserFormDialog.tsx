import React, { useEffect, useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  OutlinedInput,
  Chip,
  Box,
  CircularProgress,
  Alert,
} from '@mui/material';
import { useForm, Controller } from 'react-hook-form';
import { User, UserCreate, UserUpdate } from '../../types/user.types';
import { workspaceService } from '../../api/services/workspace.service';
import { useAuthStore } from '../../store/authStore';

interface UserFormDialogProps {
  open: boolean;
  user: User | null;
  onClose: () => void;
  onSubmit: (data: UserCreate | UserUpdate) => Promise<void>;
}

export const UserFormDialog: React.FC<UserFormDialogProps> = ({ open, user, onClose, onSubmit }) => {
  const { register, handleSubmit, formState, reset, control } = useForm<UserCreate | UserUpdate>({
    defaultValues: { username: '', password: '', roles: [] as string[] } as UserCreate,
  });

  const { errors } = formState;
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [availableWorkspaces, setAvailableWorkspaces] = useState<string[]>([]);
  const [loadingWorkspaces, setLoadingWorkspaces] = useState(false);
  const currentUser = useAuthStore(state => state.user);
  const isSuperAdmin = currentUser?.username === 'admin';
  const isEditMode = !!user;

  useEffect(() => {
    if (user) {
      reset({ username: user.username, password: '', roles: user.roles, workspace: user.workspace });
    } else {
      reset({ username: '', password: '', roles: [], workspace: undefined });
    }
  }, [user, reset]);

  useEffect(() => {
    // Only load workspaces if super admin and dialog is open
    if (open && isSuperAdmin) {
      const loadWorkspaces = async () => {
        setLoadingWorkspaces(true);
        try {
          const workspaces = await workspaceService.getWorkspaces();
          setAvailableWorkspaces(workspaces.map(w => w.name));
        } catch (error) {
          console.error('Failed to load workspaces:', error);
          setAvailableWorkspaces([]);
        } finally {
          setLoadingWorkspaces(false);
        }
      };
      loadWorkspaces();
    }
  }, [open, isSuperAdmin]);

  const availableRoles = ['admin', 'sapro_admin', 'cc_admin'];

  const handleFormSubmit = async (data: UserCreate | UserUpdate) => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const payload: any = { ...data };
      if (isEditMode) {
        // If editing and password is empty, don't send the password field
        if (!payload.password) {
          delete payload.password;
        }
      }
      await onSubmit(payload);
      reset({ username: '', password: '', roles: [], workspace: undefined });
      onClose();
      setErrorMessage(null);
    } catch (error: any) {
      // Extract meaningful message from axios / FastAPI validation errors
      let message = 'Failed to save user';
      if (error?.response?.data?.detail) {
        const detail = error.response.data.detail;
        if (Array.isArray(detail)) {
          // FastAPI validation error format: [{loc, msg, type}, ...]
          message = detail.map((err: any) => err.msg).join(', ');
          // Make validation messages more user-friendly
          message = message.replace(/String should have/g, 'Password should have');
        } else if (typeof detail === 'string') {
          message = detail;
        }
      } else if (error.message) {
        message = error.message;
      }

      // Set the error message so the user can see it in the dialog and fix inputs.
      setErrorMessage(message);
      // Do not rethrow the error; keep the dialog open.
      console.error('User form submit error', error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth scroll="body" PaperProps={{ sx: { margin: '32px' } }}>
      <DialogTitle>{isEditMode ? 'Edit User' : 'Create User'}</DialogTitle>
      <DialogContent sx={{ paddingTop: '24px !important', paddingBottom: '24px' }}>
        {errorMessage && (
          <Alert severity="error" sx={{ marginBottom: 2 }} onClose={() => setErrorMessage(null)}>
            {errorMessage}
          </Alert>
        )}
        <form id="user-form" onSubmit={handleSubmit(handleFormSubmit)}>
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr', gap: 2 }}>
            <TextField
              label="Username"
              fullWidth
              disabled={isEditMode}
              {...register('username', { required: 'Username is required' })}
              error={!!(errors as any)?.username}
              helperText={(errors as any)?.username?.message}
            />

            <TextField
              label="Password"
              type="password"
              fullWidth
              {...register('password', isEditMode ? {} : { required: 'Password is required' })}
              error={!!(errors as any)?.password}
              helperText={isEditMode ? 'Leave blank to keep current password' : 'Minimum 8 characters required'}
            />

            <FormControl fullWidth>
              <InputLabel id="roles-label">Roles</InputLabel>
              <Controller
                control={control}
                name="roles"
                rules={{ required: 'At least one role is required' }}
                render={({ field }) => (
                  <Select
                    labelId="roles-label"
                    multiple
                    value={field.value || []}
                    onChange={(e) => field.onChange(e.target.value)}
                    input={<OutlinedInput label="Roles" />}
                    renderValue={(selected) => (
                      <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                        {(selected as string[]).map((value) => (
                          <Chip key={value} label={value} size="small" />
                        ))}
                      </Box>
                    )}
                  >
                    {availableRoles.map((role) => (
                      <MenuItem key={role} value={role}>
                        {role}
                      </MenuItem>
                    ))}
                  </Select>
                )}
              />
            </FormControl>

            {isSuperAdmin && (
              <FormControl fullWidth>
                <InputLabel id="workspace-label">Workspace</InputLabel>
                <Controller
                  control={control}
                  name="workspace"
                  render={({ field }) => (
                    <Select
                      labelId="workspace-label"
                      value={field.value || ''}
                      onChange={(e) => field.onChange(e.target.value)}
                      label="Workspace"
                      disabled={loadingWorkspaces}
                    >
                      {availableWorkspaces.map((workspace) => (
                        <MenuItem key={workspace} value={workspace}>
                          {workspace === '*' ? '* (All Workspaces)' : workspace}
                        </MenuItem>
                      ))}
                    </Select>
                  )}
                />
                {loadingWorkspaces && (
                  <Box sx={{ display: 'flex', justifyContent: 'center', mt: 1 }}>
                    <CircularProgress size={20} />
                  </Box>
                )}
              </FormControl>
            )}

          </Box>
        </form>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={isLoading}>Cancel</Button>
        <Button type="submit" form="user-form" variant="contained" disabled={isLoading}>
          {isLoading ? <CircularProgress size={20} /> : (isEditMode ? 'Save' : 'Create')}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default UserFormDialog;
