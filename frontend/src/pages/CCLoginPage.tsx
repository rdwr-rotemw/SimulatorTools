import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, TextField, Button, Typography, Paper, Alert, CircularProgress,
  IconButton, Tooltip, List, ListItemButton, ListItemIcon, ListItemText,
  ListItemSecondaryAction, Divider,
} from '@mui/material';
import { useForm } from 'react-hook-form';
import StarIcon from '@mui/icons-material/Star';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import ComputerIcon from '@mui/icons-material/Computer';
import PersonIcon from '@mui/icons-material/Person';
import { useCCStore } from '../store/ccStore';
import { Layout } from '../components/common/Layout';
import { ccFavoritesService, CCFavorite } from '../api/services/ccFavorites.service';
import { CCAddFavoriteDialog } from '../components/cc/CCAddFavoriteDialog';

interface FormValues {
  cc_ip: string;
  username: string;
  password: string;
}

export const CCLoginPage: React.FC = () => {
  const navigate = useNavigate();
  const login = useCCStore((state) => state.login);
  const isLoading = useCCStore((state) => state.isLoading);
  const error = useCCStore((state) => state.error);
  const clearError = useCCStore((state) => state.clearError);

  const { register, handleSubmit, reset } = useForm<FormValues>({
    defaultValues: { cc_ip: '', username: '', password: '' },
  });

  // Favorites state
  const [favorites, setFavorites] = useState<CCFavorite[]>([]);
  const [showAddFavoriteDialog, setShowAddFavoriteDialog] = useState(false);
  const [pendingLoginData, setPendingLoginData] = useState<FormValues | null>(null);
  const [connectingFavorite, setConnectingFavorite] = useState<string | null>(null);

  const loadFavorites = useCallback(async () => {
    try {
      const favs = await ccFavoritesService.list();
      setFavorites(favs);
    } catch (err) {
      console.error('Failed to load favorites:', err);
    }
  }, []);

  useEffect(() => {
    loadFavorites();
    return () => {
      clearError();
    };
  }, [clearError, loadFavorites]);

  const onSubmit = async (data: FormValues) => {
    try {
      const success = await login(data.cc_ip, data.username, data.password);
      if (success) {
        const alreadyFavorited = favorites.some(f => f.cc_ip === data.cc_ip);
        if (!alreadyFavorited) {
          setPendingLoginData(data);
          setShowAddFavoriteDialog(true);
        } else {
          // Update saved credentials if they changed
          const existing = favorites.find(f => f.cc_ip === data.cc_ip);
          if (existing && (existing.username !== data.username || existing.password !== data.password)) {
            try {
              await ccFavoritesService.save(data.cc_ip, data.username, data.password);
            } catch (err) {
              console.error('Failed to update favorite credentials:', err);
            }
          }
          navigate('/cc/dashboard');
        }
      }
    } catch (err) {
      // store sets error
    }
  };

  const handleFavoriteClick = async (favorite: CCFavorite) => {
    setConnectingFavorite(favorite.cc_ip);
    try {
      const success = await login(favorite.cc_ip, favorite.username, favorite.password);
      if (success) {
        navigate('/cc/dashboard');
      }
    } catch (err) {
      // Error handled by store
    } finally {
      setConnectingFavorite(null);
    }
  };

  const handleFavoriteDelete = async (cc_ip: string, event: React.MouseEvent) => {
    event.stopPropagation();
    try {
      await ccFavoritesService.remove(cc_ip);
      setFavorites(prev => prev.filter(f => f.cc_ip !== cc_ip));
    } catch (err) {
      console.error('Failed to delete favorite:', err);
    }
  };

  const handleAddFavoriteConfirm = async () => {
    if (pendingLoginData) {
      await ccFavoritesService.save(
        pendingLoginData.cc_ip,
        pendingLoginData.username,
        pendingLoginData.password
      );
    }
  };

  const handleAddFavoriteClose = () => {
    setShowAddFavoriteDialog(false);
    setPendingLoginData(null);
    navigate('/cc/dashboard');
  };

  return (
    <Layout>
      <Box sx={{
        minHeight: '100vh',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        padding: '20px',
        background: 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)',
      }}>
        <Box sx={{
          display: 'flex',
          gap: 3,
          maxWidth: favorites.length > 0 ? '900px' : '500px',
          width: '100%',
          alignItems: 'stretch',
          transition: 'max-width 0.3s ease',
        }}>
          {/* Favorites Panel */}
          {favorites.length > 0 && (
            <Paper sx={{
              width: '340px',
              minWidth: '340px',
              borderRadius: '12px',
              boxShadow: '0 20px 60px rgba(0,0,0,0.1)',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
            }}>
              <Box sx={{
                padding: '24px 24px 16px',
                background: 'linear-gradient(135deg, #0052CC 0%, #0747A6 100%)',
                color: 'white',
              }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, marginBottom: 0.5 }}>
                  <StarIcon sx={{ fontSize: 22 }} />
                  <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '18px' }}>
                    Favorites
                  </Typography>
                </Box>
                <Typography variant="body2" sx={{ opacity: 0.8, fontSize: '13px' }}>
                  Click to connect instantly
                </Typography>
              </Box>

              <List sx={{
                flex: 1,
                overflowY: 'auto',
                padding: '8px 0',
                '& .MuiListItemButton-root:hover': {
                  backgroundColor: 'rgba(0, 82, 204, 0.06)',
                },
              }}>
                {favorites.map((fav, index) => (
                  <React.Fragment key={fav.cc_ip}>
                    {index > 0 && <Divider variant="inset" component="li" />}
                    <ListItemButton
                      onClick={() => handleFavoriteClick(fav)}
                      disabled={isLoading}
                      sx={{
                        padding: '12px 16px 12px 20px',
                        ...(connectingFavorite === fav.cc_ip && {
                          backgroundColor: 'rgba(0, 82, 204, 0.08)',
                        }),
                      }}
                    >
                      <ListItemIcon sx={{ minWidth: 40 }}>
                        {connectingFavorite === fav.cc_ip ? (
                          <CircularProgress size={22} />
                        ) : (
                          <ComputerIcon sx={{ color: '#0052CC' }} />
                        )}
                      </ListItemIcon>
                      <ListItemText
                        primary={
                          <Typography sx={{ fontWeight: 600, fontSize: '14px', color: '#172B4D' }}>
                            {fav.cc_ip}
                          </Typography>
                        }
                        secondary={
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, marginTop: 0.25 }}>
                            <PersonIcon sx={{ fontSize: 14, color: '#999' }} />
                            <Typography variant="caption" sx={{ color: '#666' }}>
                              {fav.username}
                            </Typography>
                          </Box>
                        }
                      />
                      <ListItemSecondaryAction>
                        <Tooltip title="Remove">
                          <IconButton
                            edge="end"
                            size="small"
                            onClick={(e) => handleFavoriteDelete(fav.cc_ip, e)}
                            sx={{
                              opacity: 0.4,
                              '&:hover': { opacity: 1, color: '#de350b' },
                              transition: 'opacity 0.2s, color 0.2s',
                            }}
                          >
                            <DeleteOutlineIcon sx={{ fontSize: 18 }} />
                          </IconButton>
                        </Tooltip>
                      </ListItemSecondaryAction>
                    </ListItemButton>
                  </React.Fragment>
                ))}
              </List>
            </Paper>
          )}

          {/* Login Form */}
          <Paper sx={{
            flex: 1,
            padding: '60px 40px',
            borderRadius: '12px',
            boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
          }}>
            <Box sx={{ marginBottom: 3, display: 'flex', justifyContent: 'center' }}>
              <img
                src="/assets/images/radware-logo.jpg"
                alt="Radware"
                style={{ height: '60px' }}
              />
            </Box>

            <Typography variant="h1" sx={{ fontSize: '42px', fontWeight: 700, color: '#0052CC', textAlign: 'center', marginBottom: '15px', letterSpacing: '-0.5px' }}>
              CyberController Login
            </Typography>

            <Typography sx={{ fontSize: '18px', color: '#666', textAlign: 'center', marginBottom: '40px' }}>
              Connect to CyberController
            </Typography>

            {error && (
              <Alert severity="error" sx={{ marginBottom: 2 }}>{error}</Alert>
            )}

            <form onSubmit={handleSubmit(onSubmit)}>
              <Box sx={{ display: 'grid', gap: 2 }}>
                <TextField label="CC IP Address" fullWidth required {...register('cc_ip', { required: true })} />
                <TextField label="Username" fullWidth required {...register('username', { required: true })} />
                <TextField label="Password" fullWidth type="password" required {...register('password', { required: true })} />

                <Button type="submit" fullWidth sx={{ background: '#0052CC', color: 'white', '&:hover': { background: '#0047b3' } }} disabled={isLoading}>
                  {isLoading ? <CircularProgress size={20} color="inherit" /> : 'LOGIN'}
                </Button>
              </Box>
            </form>
          </Paper>
        </Box>
      </Box>

      <CCAddFavoriteDialog
        open={showAddFavoriteDialog}
        onClose={handleAddFavoriteClose}
        onConfirm={handleAddFavoriteConfirm}
        ccIp={pendingLoginData?.cc_ip ?? ''}
      />
    </Layout>
  );
};
