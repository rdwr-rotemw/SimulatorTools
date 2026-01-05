import React from 'react';
import {
  Box,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Typography,
  IconButton,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import AutorenewIcon from '@mui/icons-material/Autorenew';
import { SNMPTrap, SNMPFormErrors } from '../../types/snmp.types';
import {
  AttackCategory,
  AttackProtocol,
  AttackStatus,
  AttackRisk,
  AttackAction,
  AttackDirection,
  SNMP_FIELD_DEFAULTS,
} from '../../constants/snmp.constants';
import {
  generateRadwareId,
  generateAttackId,
} from '../../utils/snmp.utils';

interface SNMPTrapFormProps {
  trap: SNMPTrap;
  onChange: (trap: SNMPTrap) => void;
  errors: SNMPFormErrors;
}

export const SNMPTrapForm: React.FC<SNMPTrapFormProps> = ({ trap, onChange, errors }) => {
  const handleFieldChange = (field: keyof SNMPTrap, value: any) => {
    onChange({ ...trap, [field]: value });
  };

  return (
    <Box>
      <Typography variant="h6" sx={{ mb: 2 }}>
        Trap Configuration
      </Typography>

      <Grid container spacing={2}>
        {/* Row 1 - Required Fields */}
        <Grid size={{ xs: 12, md: 6 }}>
          <TextField
            label="Attack Name"
            required
            fullWidth
            value={trap.attackName}
            onChange={(e) => handleFieldChange('attackName', e.target.value)}
            error={!!errors.attackName}
            helperText={errors.attackName}
          />
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          <TextField
            label="Policy"
            required
            fullWidth
            value={trap.policy}
            onChange={(e) => handleFieldChange('policy', e.target.value)}
            error={!!errors.policy}
            helperText={errors.policy}
          />
        </Grid>

        {/* Row 2 - IDs with Generate Buttons */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <TextField
              label="Attack ID"
              fullWidth
              value={trap.attackId || ''}
              onChange={(e) => handleFieldChange('attackId', e.target.value)}
            />
            <IconButton
              aria-label="generate-attack-id"
              onClick={() => onChange({ ...trap, attackId: generateAttackId() })}
            >
              <AutorenewIcon />
            </IconButton>
          </Box>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <TextField
              label="Radware ID"
              fullWidth
              value={trap.radwareId || ''}
              onChange={(e) => handleFieldChange('radwareId', e.target.value)}
            />
            <IconButton
              aria-label="generate-radware-id"
              onClick={() => onChange({ ...trap, radwareId: generateRadwareId() })}
            >
              <AutorenewIcon />
            </IconButton>
          </Box>
        </Grid>

        {/* Row 3 - Enums */}
        <Grid size={{ xs: 12, md: 6 }}>
          <FormControl fullWidth>
            <InputLabel id="attack-category-label">Attack Category</InputLabel>
            <Select
              labelId="attack-category-label"
              label="Attack Category"
              value={trap.attackCategory || SNMP_FIELD_DEFAULTS.attackCategory}
              onChange={(e) => handleFieldChange('attackCategory', e.target.value as AttackCategory)}
            >
              {Object.values(AttackCategory).map((val) => (
                <MenuItem key={val} value={val}>
                  {val}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <FormControl fullWidth>
            <InputLabel id="protocol-label">Protocol</InputLabel>
            <Select
              labelId="protocol-label"
              label="Protocol"
              value={trap.protocol || SNMP_FIELD_DEFAULTS.protocol}
              onChange={(e) => handleFieldChange('protocol', e.target.value as AttackProtocol)}
            >
              {Object.values(AttackProtocol).map((val) => (
                <MenuItem key={val} value={val}>
                  {val}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Grid>

        {/* Row 4 - Source */}
        <Grid size={{ xs: 12, md: 6 }}>
          <TextField
            label="Source IP"
            fullWidth
            value={trap.srcIp || SNMP_FIELD_DEFAULTS.srcIp}
            onChange={(e) => handleFieldChange('srcIp', e.target.value)}
            error={!!errors.srcIp}
            helperText={errors.srcIp}
          />
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          <TextField
            label="Source Port"
            fullWidth
            value={trap.srcPort || SNMP_FIELD_DEFAULTS.srcPort}
            onChange={(e) => handleFieldChange('srcPort', e.target.value)}
            error={!!errors.srcPort}
            helperText={errors.srcPort}
          />
        </Grid>

        {/* Row 5 - Destination */}
        <Grid size={{ xs: 12, md: 6 }}>
          <TextField
            label="Destination IP"
            fullWidth
            value={trap.dstIp || SNMP_FIELD_DEFAULTS.dstIp}
            onChange={(e) => handleFieldChange('dstIp', e.target.value)}
            error={!!errors.dstIp}
            helperText={errors.dstIp}
          />
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          <TextField
            label="Destination Port"
            fullWidth
            value={trap.dstPort || SNMP_FIELD_DEFAULTS.dstPort}
            onChange={(e) => handleFieldChange('dstPort', e.target.value)}
            error={!!errors.dstPort}
            helperText={errors.dstPort}
          />
        </Grid>

        {/* Row 6 - Status and Risk */}
        <Grid size={{ xs: 12, md: 6 }}>
          <FormControl fullWidth>
            <InputLabel id="status-label">Status</InputLabel>
            <Select
              labelId="status-label"
              label="Status"
              value={trap.status || SNMP_FIELD_DEFAULTS.status}
              onChange={(e) => handleFieldChange('status', e.target.value as AttackStatus)}
            >
              {Object.values(AttackStatus).map((val) => (
                <MenuItem key={val} value={val}>
                  {val}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <FormControl fullWidth>
            <InputLabel id="risk-label">Risk</InputLabel>
            <Select
              labelId="risk-label"
              label="Risk"
              value={trap.risk || SNMP_FIELD_DEFAULTS.risk}
              onChange={(e) => handleFieldChange('risk', e.target.value as AttackRisk)}
            >
              {Object.values(AttackRisk).map((val) => (
                <MenuItem key={val} value={val}>
                  {val}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Grid>

        {/* Row 7 - Action and Direction */}
        <Grid size={{ xs: 12, md: 6 }}>
          <FormControl fullWidth>
            <InputLabel id="action-label">Action</InputLabel>
            <Select
              labelId="action-label"
              label="Action"
              value={trap.action || SNMP_FIELD_DEFAULTS.action}
              onChange={(e) => handleFieldChange('action', e.target.value as AttackAction)}
            >
              {Object.values(AttackAction).map((val) => (
                <MenuItem key={val} value={val}>
                  {val}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <FormControl fullWidth>
            <InputLabel id="direction-label">Direction</InputLabel>
            <Select
              labelId="direction-label"
              label="Direction"
              value={trap.direction || SNMP_FIELD_DEFAULTS.direction}
              onChange={(e) => handleFieldChange('direction', e.target.value as AttackDirection)}
            >
              {Object.values(AttackDirection).map((val) => (
                <MenuItem key={val} value={val}>
                  {val}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Grid>

        {/* Row 8 - Traffic Metrics */}
        <Grid size={{ xs: 12, md: 4 }}>
          <TextField
            label="Packet Count"
            fullWidth
            value={trap.packetCount || SNMP_FIELD_DEFAULTS.packetCount}
            onChange={(e) => handleFieldChange('packetCount', e.target.value)}
          />
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <TextField
            label="Packet Bandwidth"
            fullWidth
            value={trap.packetBandwidth || SNMP_FIELD_DEFAULTS.packetBandwidth}
            onChange={(e) => handleFieldChange('packetBandwidth', e.target.value)}
          />
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <TextField
            label="Physical Port"
            fullWidth
            value={trap.physicalPort || SNMP_FIELD_DEFAULTS.physicalPort}
            onChange={(e) => handleFieldChange('physicalPort', e.target.value)}
          />
        </Grid>

        {/* Row 9 - Samples */}
        <Grid size={12}>
          <TextField
            label="Samples"
            fullWidth
            value={trap.samples || SNMP_FIELD_DEFAULTS.samples}
            onChange={(e) => handleFieldChange('samples', e.target.value)}
            helperText="Format: 0-0-0"
          />
        </Grid>

        {/* Row 10 - Pause */}
        <Grid size={12}>
          <TextField
            label="Pause After Trap (seconds)"
            type="number"
            fullWidth
            value={trap.pause ?? ''}
            onChange={(e) => {
              const val = e.target.value;
              if (val === '') {
                handleFieldChange('pause', undefined);
              } else {
                const num = parseInt(val, 10);
                const clamped = Math.max(0, Math.min(60, num));
                handleFieldChange('pause', clamped);
              }
            }}
            error={trap.pause !== undefined && (trap.pause < 0 || trap.pause > 60)}
            helperText={trap.pause !== undefined && (trap.pause < 0 || trap.pause > 60) ? 'Pause must be between 0 and 60 seconds' : 'Optional pause in seconds after sending this trap'}
            inputProps={{ min: 0, max: 60, step: 1 }}
          />
        </Grid>
      </Grid>
    </Box>
  );
};
