import React, { useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  Grid,
  Paper,
  Snackbar,
  TextField,
  Typography,
} from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import BuildIcon from '@mui/icons-material/Build';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import WarningIcon from '@mui/icons-material/Warning';
import { compileMibs, CompilationResult } from '../api/services/oidCompiler.service';

const OIDCompilerPage: React.FC = () => {
  const [mibZip, setMibZip] = useState<File | null>(null);
  const [oidsPdf, setOidsPdf] = useState<File | null>(null);
  const [outputName, setOutputName] = useState('');
  const [numRows, setNumRows] = useState(2);
  const [cmfOutputDir, setCmfOutputDir] = useState('/opt/sapro/cmf');
  const [varOutputDir, setVarOutputDir] = useState('/opt/sapro/var');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CompilationResult | null>(null);
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false,
    message: '',
    severity: 'success',
  });

  const handleCompile = async () => {
    if (!mibZip || !oidsPdf) return;

    setLoading(true);
    setResult(null);
    try {
      const compilationResult = await compileMibs(
        mibZip,
        oidsPdf,
        outputName || undefined,
        numRows,
        cmfOutputDir,
        varOutputDir,
      );
      setResult(compilationResult);
      setSnackbar({
        open: true,
        message: compilationResult.success ? 'Compilation completed successfully!' : 'Compilation failed.',
        severity: compilationResult.success ? 'success' : 'error',
      });
    } catch (err: any) {
      setSnackbar({
        open: true,
        message: err.response?.data?.detail || err.message || 'Compilation failed',
        severity: 'error',
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ p: 3, maxWidth: 900, mx: 'auto' }}>
      <Typography variant="h4" gutterBottom>
        MIB Compiler
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Compile DefensePro MIB files and OIDs PDF into SAPRO-compatible .cmf and .var files.
      </Typography>

      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Upload Files
        </Typography>
        <Grid container spacing={3}>
          <Grid item xs={12} sm={6}>
            <Button
              variant="outlined"
              component="label"
              fullWidth
              startIcon={<CloudUploadIcon />}
              sx={{ py: 2 }}
            >
              {mibZip ? mibZip.name : 'Select MIB ZIP File'}
              <input
                type="file"
                hidden
                accept=".zip"
                onChange={(e) => setMibZip(e.target.files?.[0] || null)}
              />
            </Button>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Button
              variant="outlined"
              component="label"
              fullWidth
              startIcon={<CloudUploadIcon />}
              sx={{ py: 2 }}
            >
              {oidsPdf ? oidsPdf.name : 'Select OIDs PDF File'}
              <input
                type="file"
                hidden
                accept=".pdf"
                onChange={(e) => setOidsPdf(e.target.files?.[0] || null)}
              />
            </Button>
          </Grid>
        </Grid>

        <Divider sx={{ my: 3 }} />

        <Typography variant="h6" gutterBottom>
          Configuration
        </Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6}>
            <TextField
              label="Output Name"
              value={outputName}
              onChange={(e) => setOutputName(e.target.value)}
              fullWidth
              size="small"
              helperText="Auto-detected from PDF if empty (e.g. DP_10_12)"
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <TextField
              label="Static Rows per Table"
              type="number"
              value={numRows}
              onChange={(e) => setNumRows(parseInt(e.target.value, 10) || 2)}
              fullWidth
              size="small"
              inputProps={{ min: 1, max: 100 }}
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <TextField
              label="CMF Output Directory"
              value={cmfOutputDir}
              onChange={(e) => setCmfOutputDir(e.target.value)}
              fullWidth
              size="small"
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <TextField
              label="VAR Output Directory"
              value={varOutputDir}
              onChange={(e) => setVarOutputDir(e.target.value)}
              fullWidth
              size="small"
            />
          </Grid>
        </Grid>

        <Box sx={{ mt: 3, display: 'flex', justifyContent: 'center' }}>
          <Button
            variant="contained"
            size="large"
            onClick={handleCompile}
            disabled={!mibZip || !oidsPdf || loading}
            startIcon={loading ? <CircularProgress size={20} /> : <BuildIcon />}
          >
            {loading ? 'Compiling...' : 'Compile'}
          </Button>
        </Box>
      </Paper>

      {result && (
        <Paper sx={{ p: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
            {result.success ? (
              <CheckCircleIcon color="success" />
            ) : (
              <ErrorIcon color="error" />
            )}
            <Typography variant="h6">
              {result.success ? 'Compilation Successful' : 'Compilation Failed'}
            </Typography>
            {result.version && (
              <Chip label={`v${result.version}`} size="small" color="primary" />
            )}
          </Box>

          {result.success && (
            <>
              <Typography variant="body2" sx={{ mb: 1 }}>
                <strong>CMF:</strong> {result.cmf_path}
              </Typography>
              <Typography variant="body2" sx={{ mb: 2 }}>
                <strong>VAR:</strong> {result.var_path}
              </Typography>

              <Divider sx={{ my: 2 }} />

              <Typography variant="subtitle2" gutterBottom>
                Statistics
              </Typography>
              <Grid container spacing={1}>
                {Object.entries(result.stats).map(([key, value]) => (
                  <Grid item xs={6} sm={4} md={3} key={key}>
                    <Card variant="outlined" sx={{ textAlign: 'center', p: 1 }}>
                      <CardContent sx={{ p: 1, '&:last-child': { pb: 1 } }}>
                        <Typography variant="h6">{value}</Typography>
                        <Typography variant="caption" color="text.secondary">
                          {key.replace(/_/g, ' ')}
                        </Typography>
                      </CardContent>
                    </Card>
                  </Grid>
                ))}
              </Grid>
            </>
          )}

          {result.errors.length > 0 && (
            <Box sx={{ mt: 2 }}>
              {result.errors.map((error, idx) => (
                <Alert key={idx} severity="error" sx={{ mb: 1 }}>
                  {error}
                </Alert>
              ))}
            </Box>
          )}

          {result.warnings.length > 0 && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 1 }}>
                <WarningIcon fontSize="small" color="warning" />
                Warnings ({result.warnings.length})
              </Typography>
              {result.warnings.map((warning, idx) => (
                <Alert key={idx} severity="warning" sx={{ mb: 1 }}>
                  {warning}
                </Alert>
              ))}
            </Box>
          )}
        </Paper>
      )}

      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar((s) => ({ ...s, open: false }))}
      >
        <Alert severity={snackbar.severity} onClose={() => setSnackbar((s) => ({ ...s, open: false }))}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default OIDCompilerPage;
