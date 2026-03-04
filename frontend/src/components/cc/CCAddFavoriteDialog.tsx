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
import StarIcon from '@mui/icons-material/Star';

interface CCAddFavoriteDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  ccIp: string;
}

export const CCAddFavoriteDialog: React.FC<CCAddFavoriteDialogProps> = ({
  open,
  onClose,
  onConfirm,
  ccIp,
}) => {
  const [isLoading, setIsLoading] = useState(false);

  const handleConfirm = async () => {
    setIsLoading(true);
    try {
      await onConfirm();
      onClose();
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
        <StarIcon color="primary" />
        Add to Favorites?
      </DialogTitle>
      <DialogContent>
        <DialogContentText>
          Save <strong>{ccIp}</strong> to your favorites for one-click login next time?
        </DialogContentText>
      </DialogContent>
      <DialogActions sx={{ padding: 2, gap: 1 }}>
        <Button
          variant="outlined"
          onClick={onClose}
          disabled={isLoading}
        >
          No Thanks
        </Button>
        <Button
          variant="contained"
          onClick={handleConfirm}
          disabled={isLoading}
          startIcon={isLoading ? <CircularProgress size={20} color="inherit" /> : <StarIcon />}
        >
          {isLoading ? 'Saving...' : 'Add to Favorites'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};
