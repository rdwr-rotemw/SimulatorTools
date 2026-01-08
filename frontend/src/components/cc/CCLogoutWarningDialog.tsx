import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Button,
  CircularProgress,
} from '@mui/material';
import WarningIcon from '@mui/icons-material/Warning';

interface CCLogoutWarningDialogProps {
  open: boolean;
  onClose: () => void;
  onLogoutAndLeave: () => Promise<void>;
  ccIp: string;
}

export const CCLogoutWarningDialog: React.FC<CCLogoutWarningDialogProps> = ({
  open,
  onClose,
  onLogoutAndLeave,
  ccIp,
}) => {
  const [isLoading, setIsLoading] = useState(false);

  const handleLogout = async () => {
    setIsLoading(true);
    try {
      await onLogoutAndLeave();
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={isLoading ? undefined : onClose}
      maxWidth="sm"
      fullWidth
    >
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <WarningIcon color="warning" />
        CyberController Session Active
      </DialogTitle>
      <DialogContent>
        <DialogContentText>
          You are still logged into CyberController at <strong>{ccIp}</strong>. Do you want to logout from CC first?
        </DialogContentText>
      </DialogContent>
      <DialogActions sx={{ padding: 2, gap: 1 }}>
        <Button
          variant="outlined"
          onClick={onClose}
          disabled={isLoading}
        >
          Stay Here
        </Button>
        <Button
          variant="contained"
          color="warning"
          onClick={handleLogout}
          disabled={isLoading}
          startIcon={isLoading ? <CircularProgress size={20} color="inherit" /> : null}
        >
          {isLoading ? 'Logging out...' : 'Logout & Leave'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};
