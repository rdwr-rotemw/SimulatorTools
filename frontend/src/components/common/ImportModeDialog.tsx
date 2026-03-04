import React from 'react';
import {
    Button,
    Dialog,
    DialogActions,
    DialogContent,
    DialogContentText,
    DialogTitle,
} from '@mui/material';
import WarningIcon from '@mui/icons-material/Warning';

interface ImportModeDialogProps {
    open: boolean;
    onClose: () => void;
    onReplace: () => void;
    onAdd: () => void;
    itemCount: number;
    importCount: number;
    itemLabel: string;
}

const ImportModeDialog: React.FC<ImportModeDialogProps> = ({
    open,
    onClose,
    onReplace,
    onAdd,
    itemCount,
    importCount,
    itemLabel,
}) => {
    const plural = itemCount === 1 ? itemLabel : `${itemLabel}s`;
    const importPlural = importCount === 1 ? itemLabel : `${itemLabel}s`;

    return (
        <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
            <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <WarningIcon color="warning" />
                Import Mode
            </DialogTitle>
            <DialogContent>
                <DialogContentText>
                    You have <strong>{itemCount}</strong> existing {plural}.
                    Import contains <strong>{importCount}</strong> {importPlural}.
                    <br /><br />
                    Would you like to <strong>add</strong> them to your existing {plural} or <strong>replace</strong> all?
                </DialogContentText>
            </DialogContent>
            <DialogActions sx={{ padding: 2, gap: 1 }}>
                <Button variant="outlined" onClick={onClose}>
                    Cancel
                </Button>
                <Button variant="contained" onClick={onAdd}>
                    Add to Existing
                </Button>
                <Button variant="contained" color="warning" onClick={onReplace}>
                    Replace All
                </Button>
            </DialogActions>
        </Dialog>
    );
};

export default ImportModeDialog;
