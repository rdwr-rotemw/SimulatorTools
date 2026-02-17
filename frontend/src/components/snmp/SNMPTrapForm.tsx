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
  Checkbox,
  FormControlLabel,
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

  const isRandom = (field: string) => (trap.randomFields || []).includes(field);

  const toggleRandom = (field: string) => {
    const current = trap.randomFields || [];
    const updated = current.includes(field)
      ? current.filter(f => f !== field)
      : [...current, field];
    onChange({ ...trap, randomFields: updated });
  };

  const RandomCheckbox = ({ field }: { field: string }) => (
    <FormControlLabel
      control={
        <Checkbox
          size="small"
          checked={isRandom(field)}
          onChange={() => toggleRandom(field)}
          sx={{ padding: '4px' }}
        />
      }
      label="R"
      sx={{ margin: 0, minWidth: 'fit-content', userSelect: 'none' }}
    />
  );

  return (
    <Box>
      <Typography variant="h6" sx={{ mb: 2 }}>
        Trap Configuration
      </Typography>

      <Grid container spacing={2}>
        {/* Row 1 - Required Fields */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
            <TextField
              label="Attack Name"
              required={!isRandom('attackName')}
              fullWidth
              value={isRandom('attackName') ? '' : trap.attackName}
              onChange={(e) => handleFieldChange('attackName', e.target.value)}
              error={!!errors.attackName}
              helperText={errors.attackName}
              disabled={isRandom('attackName')}
              placeholder={isRandom('attackName') ? 'Random (e.g. Attack_1234)' : undefined}
            />
            <Box sx={{ pt: 1 }}><RandomCheckbox field="attackName" /></Box>
          </Box>
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
            <TextField
              label="Policy"
              required={!isRandom('policy')}
              fullWidth
              value={isRandom('policy') ? '' : trap.policy}
              onChange={(e) => handleFieldChange('policy', e.target.value)}
              error={!!errors.policy}
              helperText={errors.policy}
              disabled={isRandom('policy')}
              placeholder={isRandom('policy') ? 'Random (e.g. pol42)' : undefined}
            />
            <Box sx={{ pt: 1 }}><RandomCheckbox field="policy" /></Box>
          </Box>
        </Grid>

        {/* Row 2 - IDs with Generate Buttons */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <TextField
              label="Attack ID"
              fullWidth
              value={isRandom('attackId') ? '' : (trap.attackId || '')}
              onChange={(e) => handleFieldChange('attackId', e.target.value)}
              disabled={isRandom('attackId')}
              placeholder={isRandom('attackId') ? 'Random' : undefined}
            />
            <IconButton
              aria-label="generate-attack-id"
              onClick={() => onChange({ ...trap, attackId: generateAttackId() })}
              disabled={isRandom('attackId')}
            >
              <AutorenewIcon />
            </IconButton>
            <RandomCheckbox field="attackId" />
          </Box>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <TextField
              label="Radware ID"
              fullWidth
              value={isRandom('radwareId') ? '' : (trap.radwareId || '')}
              onChange={(e) => handleFieldChange('radwareId', e.target.value)}
              disabled={isRandom('radwareId')}
              placeholder={isRandom('radwareId') ? 'Random' : undefined}
            />
            <IconButton
              aria-label="generate-radware-id"
              onClick={() => onChange({ ...trap, radwareId: generateRadwareId() })}
              disabled={isRandom('radwareId')}
            >
              <AutorenewIcon />
            </IconButton>
            <RandomCheckbox field="radwareId" />
          </Box>
        </Grid>

        {/* Row 3 - Enums */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <FormControl fullWidth disabled={isRandom('attackCategory')}>
              <InputLabel id="attack-category-label" shrink={isRandom('attackCategory') || undefined}>Attack Category</InputLabel>
              <Select
                labelId="attack-category-label"
                label="Attack Category"
                notched={isRandom('attackCategory') || undefined}
                value={isRandom('attackCategory') ? '' : (trap.attackCategory || SNMP_FIELD_DEFAULTS.attackCategory)}
                onChange={(e) => handleFieldChange('attackCategory', e.target.value as AttackCategory)}
                displayEmpty={isRandom('attackCategory')}
                renderValue={isRandom('attackCategory') ? () => <em style={{ color: '#999' }}>Random</em> : undefined}
              >
                {Object.values(AttackCategory).map((val) => (
                  <MenuItem key={val} value={val}>
                    {val}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <RandomCheckbox field="attackCategory" />
          </Box>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <FormControl fullWidth disabled={isRandom('protocol')}>
              <InputLabel id="protocol-label" shrink={isRandom('protocol') || undefined}>Protocol</InputLabel>
              <Select
                labelId="protocol-label"
                label="Protocol"
                notched={isRandom('protocol') || undefined}
                value={isRandom('protocol') ? '' : (trap.protocol || SNMP_FIELD_DEFAULTS.protocol)}
                onChange={(e) => handleFieldChange('protocol', e.target.value as AttackProtocol)}
                displayEmpty={isRandom('protocol')}
                renderValue={isRandom('protocol') ? () => <em style={{ color: '#999' }}>Random</em> : undefined}
              >
                {Object.values(AttackProtocol).map((val) => (
                  <MenuItem key={val} value={val}>
                    {val}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <RandomCheckbox field="protocol" />
          </Box>
        </Grid>

        {/* Row 4 - Source */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
            <TextField
              label="Source IP"
              fullWidth
              value={isRandom('srcIp') ? '' : (trap.srcIp || SNMP_FIELD_DEFAULTS.srcIp)}
              onChange={(e) => handleFieldChange('srcIp', e.target.value)}
              error={!!errors.srcIp}
              helperText={errors.srcIp}
              disabled={isRandom('srcIp')}
              placeholder={isRandom('srcIp') ? 'Random' : undefined}
            />
            <Box sx={{ pt: 1 }}><RandomCheckbox field="srcIp" /></Box>
          </Box>
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
            <TextField
              label="Source Port"
              fullWidth
              value={isRandom('srcPort') ? '' : (trap.srcPort || SNMP_FIELD_DEFAULTS.srcPort)}
              onChange={(e) => handleFieldChange('srcPort', e.target.value)}
              error={!!errors.srcPort}
              helperText={errors.srcPort}
              disabled={isRandom('srcPort')}
              placeholder={isRandom('srcPort') ? 'Random' : undefined}
            />
            <Box sx={{ pt: 1 }}><RandomCheckbox field="srcPort" /></Box>
          </Box>
        </Grid>

        {/* Row 5 - Destination */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
            <TextField
              label="Destination IP"
              fullWidth
              value={isRandom('dstIp') ? '' : (trap.dstIp || SNMP_FIELD_DEFAULTS.dstIp)}
              onChange={(e) => handleFieldChange('dstIp', e.target.value)}
              error={!!errors.dstIp}
              helperText={errors.dstIp}
              disabled={isRandom('dstIp')}
              placeholder={isRandom('dstIp') ? 'Random' : undefined}
            />
            <Box sx={{ pt: 1 }}><RandomCheckbox field="dstIp" /></Box>
          </Box>
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
            <TextField
              label="Destination Port"
              fullWidth
              value={isRandom('dstPort') ? '' : (trap.dstPort || SNMP_FIELD_DEFAULTS.dstPort)}
              onChange={(e) => handleFieldChange('dstPort', e.target.value)}
              error={!!errors.dstPort}
              helperText={errors.dstPort}
              disabled={isRandom('dstPort')}
              placeholder={isRandom('dstPort') ? 'Random' : undefined}
            />
            <Box sx={{ pt: 1 }}><RandomCheckbox field="dstPort" /></Box>
          </Box>
        </Grid>

        {/* Row 6 - Status and Risk */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <FormControl fullWidth disabled={isRandom('status')}>
              <InputLabel id="status-label" shrink={isRandom('status') || undefined}>Status</InputLabel>
              <Select
                labelId="status-label"
                label="Status"
                notched={isRandom('status') || undefined}
                value={isRandom('status') ? '' : (trap.status || SNMP_FIELD_DEFAULTS.status)}
                onChange={(e) => handleFieldChange('status', e.target.value as AttackStatus)}
                displayEmpty={isRandom('status')}
                renderValue={isRandom('status') ? () => <em style={{ color: '#999' }}>Random</em> : undefined}
              >
                {Object.values(AttackStatus).map((val) => (
                  <MenuItem key={val} value={val}>
                    {val}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <RandomCheckbox field="status" />
          </Box>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <FormControl fullWidth disabled={isRandom('risk')}>
              <InputLabel id="risk-label" shrink={isRandom('risk') || undefined}>Risk</InputLabel>
              <Select
                labelId="risk-label"
                label="Risk"
                notched={isRandom('risk') || undefined}
                value={isRandom('risk') ? '' : (trap.risk || SNMP_FIELD_DEFAULTS.risk)}
                onChange={(e) => handleFieldChange('risk', e.target.value as AttackRisk)}
                displayEmpty={isRandom('risk')}
                renderValue={isRandom('risk') ? () => <em style={{ color: '#999' }}>Random</em> : undefined}
              >
                {Object.values(AttackRisk).map((val) => (
                  <MenuItem key={val} value={val}>
                    {val}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <RandomCheckbox field="risk" />
          </Box>
        </Grid>

        {/* Row 7 - Action and Direction */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <FormControl fullWidth disabled={isRandom('action')}>
              <InputLabel id="action-label" shrink={isRandom('action') || undefined}>Action</InputLabel>
              <Select
                labelId="action-label"
                label="Action"
                notched={isRandom('action') || undefined}
                value={isRandom('action') ? '' : (trap.action || SNMP_FIELD_DEFAULTS.action)}
                onChange={(e) => handleFieldChange('action', e.target.value as AttackAction)}
                displayEmpty={isRandom('action')}
                renderValue={isRandom('action') ? () => <em style={{ color: '#999' }}>Random</em> : undefined}
              >
                {Object.values(AttackAction).map((val) => (
                  <MenuItem key={val} value={val}>
                    {val}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <RandomCheckbox field="action" />
          </Box>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <FormControl fullWidth disabled={isRandom('direction')}>
              <InputLabel id="direction-label" shrink={isRandom('direction') || undefined}>Direction</InputLabel>
              <Select
                labelId="direction-label"
                label="Direction"
                notched={isRandom('direction') || undefined}
                value={isRandom('direction') ? '' : (trap.direction || SNMP_FIELD_DEFAULTS.direction)}
                onChange={(e) => handleFieldChange('direction', e.target.value as AttackDirection)}
                displayEmpty={isRandom('direction')}
                renderValue={isRandom('direction') ? () => <em style={{ color: '#999' }}>Random</em> : undefined}
              >
                {Object.values(AttackDirection).map((val) => (
                  <MenuItem key={val} value={val}>
                    {val}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <RandomCheckbox field="direction" />
          </Box>
        </Grid>

        {/* Row 8 - Traffic Metrics */}
        <Grid size={{ xs: 12, md: 4 }}>
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
            <TextField
              label="Packet Count"
              fullWidth
              value={isRandom('packetCount') ? '' : (trap.packetCount || SNMP_FIELD_DEFAULTS.packetCount)}
              onChange={(e) => handleFieldChange('packetCount', e.target.value)}
              disabled={isRandom('packetCount')}
              placeholder={isRandom('packetCount') ? 'Random' : undefined}
            />
            <Box sx={{ pt: 1 }}><RandomCheckbox field="packetCount" /></Box>
          </Box>
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
            <TextField
              label="Packet Bandwidth"
              fullWidth
              value={isRandom('packetBandwidth') ? '' : (trap.packetBandwidth || SNMP_FIELD_DEFAULTS.packetBandwidth)}
              onChange={(e) => handleFieldChange('packetBandwidth', e.target.value)}
              disabled={isRandom('packetBandwidth')}
              placeholder={isRandom('packetBandwidth') ? 'Random' : undefined}
            />
            <Box sx={{ pt: 1 }}><RandomCheckbox field="packetBandwidth" /></Box>
          </Box>
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
            <TextField
              label="Physical Port"
              fullWidth
              value={isRandom('physicalPort') ? '' : (trap.physicalPort || SNMP_FIELD_DEFAULTS.physicalPort)}
              onChange={(e) => handleFieldChange('physicalPort', e.target.value)}
              disabled={isRandom('physicalPort')}
              placeholder={isRandom('physicalPort') ? 'Random' : undefined}
            />
            <Box sx={{ pt: 1 }}><RandomCheckbox field="physicalPort" /></Box>
          </Box>
        </Grid>

        {/* Row 9 - Samples */}
        <Grid size={12}>
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
            <TextField
              label="Samples"
              fullWidth
              value={isRandom('samples') ? '' : (trap.samples || SNMP_FIELD_DEFAULTS.samples)}
              onChange={(e) => handleFieldChange('samples', e.target.value)}
              helperText={isRandom('samples') ? 'Random (e.g. 42-17-8)' : 'Format: 0-0-0'}
              disabled={isRandom('samples')}
              placeholder={isRandom('samples') ? 'Random' : undefined}
            />
            <Box sx={{ pt: 1 }}><RandomCheckbox field="samples" /></Box>
          </Box>
        </Grid>

        {/* Row 10 - Pause (no Random checkbox - operational field) */}
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
