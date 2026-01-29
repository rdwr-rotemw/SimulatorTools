import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Alert,
  Tabs,
  Tab,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TextField,
  IconButton,
  Box,
  Typography,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import CasinoIcon from '@mui/icons-material/Casino';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';

export interface IRPMessage {
  messageType: string;
  messageName: string;
  data: Record<string, any>;
  schema: Record<string, any>;
  originalSchema: Record<string, any>;
  pause?: number;
}

interface AttackIdLocation {
  path: string[]; // Path to the field in the data object
  displayPath: string; // Human-readable path for display
  currentValue: string; // Current attack-ID value
  isMessage1: boolean; // Whether this is Message 1 (separate attack-id and time)
}

interface MessageAttackIds {
  messageName: string;
  messageIndex: number;
  locations: AttackIdLocation[];
}

interface IRPAttackIdConfigDialogProps {
  open: boolean;
  onClose: () => void;
  simulators: string[];
  messages: IRPMessage[];
  onConfirm: (attackIdConfig: Record<string, IRPMessage[]>) => void;
}

const IRPAttackIdConfigDialog: React.FC<IRPAttackIdConfigDialogProps> = ({
  open,
  onClose,
  simulators,
  messages,
  onConfirm
}) => {
  const [currentTab, setCurrentTab] = useState(0);
  const [modifiedMessages, setModifiedMessages] = useState<Record<string, IRPMessage[]>>({});

  // Generate a random attack-ID
  const generateRandomAttackId = (): string => {
    const prefix = Math.floor(Math.random() * 9000) + 100; // 100-9999
    const suffix = Math.floor(Math.random() * 9000000000) + 1000000000; // 10 digits
    return `${prefix}-${suffix}`;
  };

  // Generate random time (for Message 1)
  const generateRandomTime = (): string => {
    return Math.floor(Math.random() * 9000000000 + 1000000000).toString();
  };

  // Check if message is Message 1 (has separate attack-id and time fields)
  const isMessage1 = (messageType: string): boolean => {
    return messageType === '1' || messageType === '01';
  };

  // Find all attack-ID locations in a message data object
  const findAttackIdLocations = (
    data: any,
    schema: any,
    path: string[] = [],
    displayPath: string[] = [],
    messageType: string
  ): AttackIdLocation[] => {
    const locations: AttackIdLocation[] = [];

    if (!data || typeof data !== 'object') return locations;

    // Check if current level has attack-id (combined format for Message 2+)
    if ('attack-id' in data && !isMessage1(messageType)) {
      locations.push({
        path: [...path, 'attack-id'],
        displayPath: displayPath.length > 0 ? displayPath.join(' > ') + ' > attack-id' : 'attack-id',
        currentValue: data['attack-id'],
        isMessage1: false,
      });
    }

    // Check for Message 1 format (separate attack-id and time)
    if (isMessage1(messageType) && 'attack-id' in data && 'time' in data) {
      const combinedValue = `${data['attack-id']}-${data['time']}`;
      locations.push({
        path: [...path], // Path to the parent object
        displayPath: displayPath.length > 0 ? displayPath.join(' > ') : 'Root',
        currentValue: combinedValue,
        isMessage1: true,
      });
    }

    // Recursively search nested objects and arrays
    Object.keys(data).forEach(key => {
      if (key === 'attack-id' || key === 'time' || key === 'cnt') {
        // Already handled above
        return;
      }

      const value = data[key];

      if (Array.isArray(value)) {
        // Handle arrays (iterations)
        value.forEach((item, index) => {
          const itemPath = [...path, key, index.toString()];
          const itemDisplayPath = [...displayPath, `${key}[${index}]`];
          locations.push(...findAttackIdLocations(item, schema, itemPath, itemDisplayPath, messageType));
        });
      } else if (value && typeof value === 'object') {
        // Handle nested objects
        const nestedPath = [...path, key];
        const nestedDisplayPath = [...displayPath, key];
        locations.push(...findAttackIdLocations(value, schema, nestedPath, nestedDisplayPath, messageType));
      }
    });

    return locations;
  };

  // Extract attack-ID information from all messages
  const extractMessageAttackIds = (msgs: IRPMessage[]): MessageAttackIds[] => {
    return msgs.map((msg, index) => ({
      messageName: msg.messageName,
      messageIndex: index,
      locations: findAttackIdLocations(msg.data, msg.schema, [], [], msg.messageType),
    })).filter(msgInfo => msgInfo.locations.length > 0); // Only include messages with attack-IDs
  };

  // Set a value in nested object by path
  const setNestedValue = (obj: any, path: string[], value: any): any => {
    if (path.length === 0) return value;

    const newObj = Array.isArray(obj) ? [...obj] : { ...obj };
    const [first, ...rest] = path;

    if (rest.length === 0) {
      newObj[first] = value;
    } else {
      newObj[first] = setNestedValue(newObj[first], rest, value);
    }

    return newObj;
  };

  // Get a value from nested object by path
  const getNestedValue = (obj: any, path: string[]): any => {
    return path.reduce((current, key) => current?.[key], obj);
  };

  // Randomize a single attack-ID location
  const randomizeSingle = (simulatorIp: string, messageIndex: number, locationPath: string[]) => {
    setModifiedMessages(prev => {
      const simMessages = [...(prev[simulatorIp] || messages)];
      const message = { ...simMessages[messageIndex] };
      const newData = { ...message.data };

      const location = extractMessageAttackIds([message])[0]?.locations.find(
        loc => JSON.stringify(loc.path) === JSON.stringify(locationPath)
      );

      if (location?.isMessage1) {
        // Message 1: randomize both attack-id and time separately
        const newAttackId = Math.floor(Math.random() * 9000) + 100; // 100-9999
        const newTime = generateRandomTime();

        let updated = setNestedValue(newData, [...locationPath, 'attack-id'], newAttackId.toString());
        updated = setNestedValue(updated, [...locationPath, 'time'], newTime);

        message.data = updated;
      } else {
        // Other messages: randomize combined attack-id
        const newAttackId = generateRandomAttackId();
        message.data = setNestedValue(newData, locationPath, newAttackId);
      }

      simMessages[messageIndex] = message;
      return {
        ...prev,
        [simulatorIp]: simMessages,
      };
    });
  };

  // Randomize all attack-IDs for a specific message
  const randomizeMessage = (simulatorIp: string, messageIndex: number) => {
    setModifiedMessages(prev => {
      const simMessages = [...(prev[simulatorIp] || messages)];
      const message = { ...simMessages[messageIndex] };
      let newData = { ...message.data };

      const locations = extractMessageAttackIds([message])[0]?.locations || [];

      locations.forEach(location => {
        if (location.isMessage1) {
          const newAttackId = Math.floor(Math.random() * 9000) + 100;
          const newTime = generateRandomTime();
          newData = setNestedValue(newData, [...location.path, 'attack-id'], newAttackId.toString());
          newData = setNestedValue(newData, [...location.path, 'time'], newTime);
        } else {
          const newAttackId = generateRandomAttackId();
          newData = setNestedValue(newData, location.path, newAttackId);
        }
      });

      message.data = newData;
      simMessages[messageIndex] = message;

      return {
        ...prev,
        [simulatorIp]: simMessages,
      };
    });
  };

  // Randomize all attack-IDs for current simulator
  const randomizeAllForSimulator = () => {
    const simulatorIp = simulators[currentTab];
    const messagesWithAttackIds = extractMessageAttackIds(messages);

    setModifiedMessages(prev => {
      const simMessages = [...(prev[simulatorIp] || messages)].map(msg => ({ ...msg }));

      messagesWithAttackIds.forEach(msgInfo => {
        let newData = { ...simMessages[msgInfo.messageIndex].data };

        msgInfo.locations.forEach(location => {
          if (location.isMessage1) {
            const newAttackId = Math.floor(Math.random() * 9000) + 100;
            const newTime = generateRandomTime();
            newData = setNestedValue(newData, [...location.path, 'attack-id'], newAttackId.toString());
            newData = setNestedValue(newData, [...location.path, 'time'], newTime);
          } else {
            const newAttackId = generateRandomAttackId();
            newData = setNestedValue(newData, location.path, newAttackId);
          }
        });

        simMessages[msgInfo.messageIndex].data = newData;
      });

      return {
        ...prev,
        [simulatorIp]: simMessages,
      };
    });
  };

  // Randomize all non-original simulators
  const randomizeAllSimulators = () => {
    simulators.slice(1).forEach(simulatorIp => {
      const messagesWithAttackIds = extractMessageAttackIds(messages);

      setModifiedMessages(prev => {
        const simMessages = messages.map(msg => ({ ...msg, data: { ...msg.data } }));

        messagesWithAttackIds.forEach(msgInfo => {
          let newData = { ...simMessages[msgInfo.messageIndex].data };

          msgInfo.locations.forEach(location => {
            if (location.isMessage1) {
              const newAttackId = Math.floor(Math.random() * 9000) + 100;
              const newTime = generateRandomTime();
              newData = setNestedValue(newData, [...location.path, 'attack-id'], newAttackId.toString());
              newData = setNestedValue(newData, [...location.path, 'time'], newTime);
            } else {
              const newAttackId = generateRandomAttackId();
              newData = setNestedValue(newData, location.path, newAttackId);
            }
          });

          simMessages[msgInfo.messageIndex].data = newData;
        });

        return {
          ...prev,
          [simulatorIp]: simMessages,
        };
      });
    });
  };

  // Initialize/reset state when dialog opens
  useEffect(() => {
    if (open && simulators.length > 0 && messages.length > 0) {
      const initial: Record<string, IRPMessage[]> = {};

      // First simulator: keep original messages
      initial[simulators[0]] = messages.map(msg => ({ ...msg }));

      // Other simulators: randomize attack-IDs
      if (simulators.length > 1) {
        simulators.slice(1).forEach(ip => {
          const messagesWithAttackIds = extractMessageAttackIds(messages);
          const simMessages = messages.map(msg => ({ ...msg, data: { ...msg.data } }));

          messagesWithAttackIds.forEach(msgInfo => {
            let newData = { ...simMessages[msgInfo.messageIndex].data };

            msgInfo.locations.forEach(location => {
              if (location.isMessage1) {
                const newAttackId = Math.floor(Math.random() * 9000) + 100;
                const newTime = generateRandomTime();
                newData = setNestedValue(newData, [...location.path, 'attack-id'], newAttackId.toString());
                newData = setNestedValue(newData, [...location.path, 'time'], newTime);
              } else {
                const newAttackId = generateRandomAttackId();
                newData = setNestedValue(newData, location.path, newAttackId);
              }
            });

            simMessages[msgInfo.messageIndex].data = newData;
          });

          initial[ip] = simMessages;
        });
      }

      setModifiedMessages(initial);
      setCurrentTab(0);
    }
  }, [open, simulators, messages]);

  const handleConfirm = () => {
    onConfirm(modifiedMessages);
  };

  const currentSimulatorIp = simulators[currentTab];
  const currentMessages = modifiedMessages[currentSimulatorIp] || messages;
  const messagesWithAttackIds = extractMessageAttackIds(currentMessages);

  // Handle attack-ID change for a specific location
  const handleAttackIdChange = (messageIndex: number, locationPath: string[], newValue: string) => {
    setModifiedMessages(prev => {
      const simMessages = [...(prev[currentSimulatorIp] || messages)];
      const message = { ...simMessages[messageIndex] };
      let newData = { ...message.data };

      const location = extractMessageAttackIds([message])[0]?.locations.find(
        loc => JSON.stringify(loc.path) === JSON.stringify(locationPath)
      );

      if (location?.isMessage1) {
        // Message 1: split and set attack-id and time
        const parts = newValue.split('-');
        const attackId = parts[0] || '100';
        const time = parts[1] || '1000000000';

        newData = setNestedValue(newData, [...locationPath, 'attack-id'], attackId);
        newData = setNestedValue(newData, [...locationPath, 'time'], time);
      } else {
        // Other messages: set combined attack-id
        newData = setNestedValue(newData, locationPath, newValue);
      }

      message.data = newData;
      simMessages[messageIndex] = message;

      return {
        ...prev,
        [currentSimulatorIp]: simMessages,
      };
    });
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="lg"
      fullWidth
    >
      <DialogTitle>
        ⚠️ Multiple Simulators Selected - Attack-ID Configuration Required
      </DialogTitle>

      <DialogContent>
        <Alert severity="info" sx={{ mb: 2 }}>
          CyberController requires unique attack-IDs per simulator.
          Configure attack-IDs for each simulator below.
          <br />
          <strong>Note:</strong> Message 1 has separate attack-id and time fields, while other messages use combined attack-id format.
        </Alert>

        <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
          <Tabs
            value={currentTab}
            onChange={(e, newValue) => setCurrentTab(newValue)}
            variant="scrollable"
            scrollButtons="auto"
          >
            {simulators.map((ip, index) => (
              <Tab
                key={ip}
                label={`${ip}${index === 0 ? ' (Original)' : ''}`}
                value={index}
              />
            ))}
          </Tabs>
        </Box>

        <Box sx={{ mb: 2, display: 'flex', gap: 1 }}>
          {currentTab === 0 ? (
            <Button
              onClick={randomizeAllSimulators}
              startIcon={<CasinoIcon />}
              variant="outlined"
              size="small"
              color="secondary"
            >
              Randomize All Non-Original Simulators
            </Button>
          ) : (
            <>
              <Button
                onClick={randomizeAllForSimulator}
                startIcon={<CasinoIcon />}
                variant="outlined"
                size="small"
              >
                Randomize All for {currentSimulatorIp}
              </Button>
              <Button
                onClick={randomizeAllSimulators}
                startIcon={<CasinoIcon />}
                variant="outlined"
                size="small"
                color="secondary"
              >
                Randomize All Non-Original Simulators
              </Button>
            </>
          )}
        </Box>

        {messagesWithAttackIds.length === 0 ? (
          <Alert severity="warning">
            No messages with attack-ID fields found.
          </Alert>
        ) : (
          messagesWithAttackIds.map(msgInfo => (
            <Accordion key={msgInfo.messageIndex} defaultExpanded={messagesWithAttackIds.length === 1}>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, width: '100%' }}>
                  <Typography variant="h6">
                    {msgInfo.messageName}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    ({msgInfo.locations.length} attack-ID location{msgInfo.locations.length > 1 ? 's' : ''})
                  </Typography>
                  <Box sx={{ flex: 1 }} />
                  <IconButton
                    size="small"
                    onClick={(e) => {
                      e.stopPropagation();
                      randomizeMessage(currentSimulatorIp, msgInfo.messageIndex);
                    }}
                    title="Randomize all attack-IDs in this message"
                  >
                    <CasinoIcon />
                  </IconButton>
                </Box>
              </AccordionSummary>
              <AccordionDetails>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell><strong>Location</strong></TableCell>
                      <TableCell><strong>Attack-ID</strong></TableCell>
                      <TableCell align="center"><strong>Actions</strong></TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {msgInfo.locations.map((location, locIndex) => {
                      const currentValue = location.isMessage1
                        ? `${getNestedValue(currentMessages[msgInfo.messageIndex].data, [...location.path, 'attack-id'])}-${getNestedValue(currentMessages[msgInfo.messageIndex].data, [...location.path, 'time'])}`
                        : getNestedValue(currentMessages[msgInfo.messageIndex].data, location.path);

                      return (
                        <TableRow key={locIndex}>
                          <TableCell>
                            <Typography variant="body2">
                              {location.displayPath}
                              {location.isMessage1 && (
                                <Typography variant="caption" color="primary" sx={{ ml: 1 }}>
                                  (Message 1 format)
                                </Typography>
                              )}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <TextField
                              value={currentValue || ''}
                              onChange={(e) => handleAttackIdChange(msgInfo.messageIndex, location.path, e.target.value)}
                              fullWidth
                              size="small"
                              placeholder={location.isMessage1 ? "e.g., 123-456789" : "e.g., 333-1234567890"}
                            />
                          </TableCell>
                          <TableCell align="center">
                            <IconButton
                              onClick={() => randomizeSingle(currentSimulatorIp, msgInfo.messageIndex, location.path)}
                              size="small"
                              title="Randomize this attack-ID"
                            >
                              <CasinoIcon />
                            </IconButton>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </AccordionDetails>
            </Accordion>
          ))
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          onClick={handleConfirm}
          variant="contained"
          disabled={messagesWithAttackIds.length === 0}
        >
          Send Messages
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default IRPAttackIdConfigDialog;
