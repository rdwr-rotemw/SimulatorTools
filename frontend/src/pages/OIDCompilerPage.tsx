import React, { useEffect, useState } from 'react';
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
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
import Layout from '../components/common/Layout';
import { compileMibs, listDeviceDrivers, CompilationResult } from '../api/services/oidCompiler.service';

const OIDCompilerPage: React.FC = () => {
  const [mibZip, setMibZip] = useState<File | null>(null);
  const [oidsPdf, setOidsPdf] = useState<File | null>(null);
  const [outputName, setOutputName] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CompilationResult | null>(null);
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false,
    message: '',
    severity: 'success',
  });

  // Device driver state
  const [availableDrivers, setAvailableDrivers] = useState<string[]>([]);
  const [selectedDriver, setSelectedDriver] = useState<string | null>(null);
  const [customDriverFile, setCustomDriverFile] = useState<File | null>(null);

  useEffect(() => {
    listDeviceDrivers()
      .then(setAvailableDrivers)
      .catch(() => setAvailableDrivers([]));
  }, []);

  const handleCompile = async () => {
    if (!mibZip || !oidsPdf) return;

    const driverName = customDriverFile ? undefined : (selectedDriver || undefined);
    const driverFile = customDriverFile || undefined;

    setLoading(true);
    setResult(null);
    try {
      const compilationResult = await compileMibs(
        mibZip,
        oidsPdf,
        outputName || undefined,
        driverName,
        driverFile,
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
    <Layout>
      <Box sx={{ padding: 4, maxWidth: 900, mx: 'auto' }}>
        <Typography variant="h4" gutterBottom>
          MIB Compiler
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Compile Devices MIB files and OIDs PDF into SAPRO-compatible .cmf and .var files.
        </Typography>

        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            Upload Files
          </Typography>
          <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
            <Box sx={{ flex: '1 1 45%', minWidth: 250 }}>
              <Button
                variant="outlined"
                component="label"
                fullWidth
                startIcon={<CloudUploadIcon />}
                sx={{ py: 2 }}
              >
                {mibZip ? mibZip.name : 'Select MIB Archive (.rar / .zip)'}
                <input
                  type="file"
                  hidden
                  accept=".rar,.zip"
                  onChange={(e) => setMibZip(e.target.files?.[0] || null)}
                />
              </Button>
            </Box>
            <Box sx={{ flex: '1 1 45%', minWidth: 250 }}>
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
            </Box>
          </Box>

          <Divider sx={{ my: 3 }} />

          <Typography variant="h6" gutterBottom>
            Device Driver
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'flex-start' }}>
            <Box sx={{ flex: '1 1 55%', minWidth: 250 }}>
              <Autocomplete
                options={availableDrivers}
                value={selectedDriver}
                onChange={(_, val) => {
                  setSelectedDriver(val);
                  if (val) setCustomDriverFile(null);
                }}
                disabled={!!customDriverFile}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="Select Existing Driver"
                    size="small"
                    helperText="Choose from available device drivers"
                  />
                )}
              />
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', pt: 0.5 }}>
              <Typography variant="body2" color="text.secondary" sx={{ mx: 1 }}>or</Typography>
            </Box>
            <Box sx={{ flex: '1 1 35%', minWidth: 200 }}>
              <Button
                variant="outlined"
                component="label"
                fullWidth
                startIcon={<CloudUploadIcon />}
                sx={{ py: 1 }}
              >
                {customDriverFile ? customDriverFile.name : 'Upload New Driver'}
                <input
                  type="file"
                  hidden
                  accept=".jar"
                  onChange={(e) => {
                    const file = e.target.files?.[0] || null;
                    setCustomDriverFile(file);
                    if (file) setSelectedDriver(null);
                  }}
                />
              </Button>
            </Box>
          </Box>

          <Divider sx={{ my: 3 }} />

          <TextField
            label="Output Name"
            value={outputName}
            onChange={(e) => setOutputName(e.target.value)}
            fullWidth
            size="small"
            helperText="Auto-detected from PDF if empty (e.g. DP_10_12_01)"
          />

          <Box sx={{ mt: 3, display: 'flex', justifyContent: 'center' }}>
            <Button
              variant="contained"
              size="large"
              onClick={handleCompile}
              disabled={!mibZip || !oidsPdf || (!selectedDriver && !customDriverFile) || loading}
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
                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                  {Object.entries(result.stats).map(([key, value]) => (
                    <Card key={key} variant="outlined" sx={{ textAlign: 'center', p: 1, minWidth: 120, flex: '1 1 auto' }}>
                      <CardContent sx={{ p: 1, '&:last-child': { pb: 1 } }}>
                        <Typography variant="h6">{value}</Typography>
                        <Typography variant="caption" color="text.secondary">
                          {key.replace(/_/g, ' ')}
                        </Typography>
                      </CardContent>
                    </Card>
                  ))}
                </Box>
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
    </Layout>
  );
};

export default OIDCompilerPage;
