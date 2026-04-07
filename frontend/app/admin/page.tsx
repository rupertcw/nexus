"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { 
  Box, 
  Container, 
  Grid, 
  Card, 
  CardContent, 
  Typography, 
  Table, 
  TableBody, 
  TableCell, 
  TableContainer, 
  TableHead, 
  TableRow, 
  Paper,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  IconButton
} from "@mui/material";
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import RefreshIcon from '@mui/icons-material/Refresh';
import styles from "../page.module.css";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const MOCK_JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxLCJzdWIiOiJ0ZXN0X3VzZXIifQ.dummy_signature";

// Mock admin check
const useAdminGuard = () => {
  // Hardcoded true for this implementation step
  return true;
};

// Row component with expandable details
function Row({ job, onRetry }: { job: any, onRetry: (id: string) => void }) {
  const [open, setOpen] = useState(false);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'finished': return 'success';
      case 'failed': return 'error';
      case 'started': return 'warning';
      default: return 'default';
    }
  };

  return (
    <>
      <TableRow sx={{ '& > *': { borderBottom: 'unset' } }}>
        <TableCell>
          <IconButton aria-label="expand row" size="small" onClick={() => setOpen(!open)}>
            {open ? <KeyboardArrowUpIcon /> : <KeyboardArrowDownIcon />}
          </IconButton>
        </TableCell>
        <TableCell component="th" scope="row">
          {job.id}
        </TableCell>
        <TableCell>{job.file}</TableCell>
        <TableCell>
          <Chip label={job.status} color={getStatusColor(job.status)} size="small" />
        </TableCell>
        <TableCell>{job.progress}%</TableCell>
        <TableCell align="right">
          {job.status === 'failed' && (
            <Button size="small" variant="outlined" color="primary" onClick={() => onRetry(job.id)}>
              Retry
            </Button>
          )}
        </TableCell>
      </TableRow>
      <TableRow>
        <TableCell style={{ paddingBottom: 0, paddingTop: 0 }} colSpan={6}>
          <Collapse in={open} timeout="auto" unmountOnExit>
            <Box sx={{ margin: 1, padding: 2, bgcolor: '#f5f5f5', borderRadius: 1 }}>
              <Typography variant="h6" gutterBottom component="div">
                Job Details
              </Typography>
              <Typography variant="body2" color="text.secondary">
                <strong>Enqueued:</strong> {job.created_at ? new Date(job.created_at).toLocaleString() : 'N/A'}<br/>
                <strong>Progress:</strong> {job.progress}%
              </Typography>
              {job.error && (
                <Box mt={2}>
                  <Typography variant="subtitle2" color="error">Traceback:</Typography>
                  <Paper sx={{ p: 1, bgcolor: '#fff0f0', maxHeight: 200, overflow: 'auto' }}>
                    <pre style={{ fontSize: '11px', margin: 0 }}>{job.error}</pre>
                  </Paper>
                </Box>
              )}
            </Box>
          </Collapse>
        </TableCell>
      </TableRow>
    </>
  );
}


export default function AdminDashboard() {
  const isAdmin = useAdminGuard();
  const queryClient = useQueryClient();

  // Polling hook for statistics
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['ingestionStats'],
    queryFn: async () => {
      const res = await fetch(`${API_URL}/ingestion/stats`, {
        headers: { "Authorization": `Bearer ${MOCK_JWT}` }
      });
      return res.json();
    },
    refetchInterval: 5000,
  });

  // Polling hook for job listed
  const { data: jobs, isLoading: jobsLoading } = useQuery({
    queryKey: ['ingestionJobs'],
    queryFn: async () => {
      const res = await fetch(`${API_URL}/ingestion/jobs`, {
        headers: { "Authorization": `Bearer ${MOCK_JWT}` }
      });
      return res.json();
    },
    refetchInterval: 5000,
  });

  // Retry mutation
  const retryMutation = useMutation({
    mutationFn: async (jobId: string) => {
      const res = await fetch(`${API_URL}/ingestion/jobs/${jobId}/retry`, {
        method: 'POST',
        headers: { "Authorization": `Bearer ${MOCK_JWT}` }
      });
      if (!res.ok) throw new Error('Failed to retry job');
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ingestionJobs'] });
      queryClient.invalidateQueries({ queryKey: ['ingestionStats'] });
    }
  });

  if (!isAdmin) {
    return <div>Access Denied</div>;
  }

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: '#f9fafb' }}>
      {/* Sidebar matching the app style */}
      <div className={styles.sidebar}>
        <div className={styles.sidebarTitle}>
          <span>AI</span> Knowledge Admin
        </div>
        
        <div style={{ marginTop: '20px' }}>
          <Link href="/">
            <button className={styles.newChatBtn} style={{ background: '#555' }}>
              &larr; Back to Chat
            </button>
          </Link>
        </div>
        
        <Box mt={4} pl={2} color="#aaa">
            <Typography variant="overline">Management</Typography>
            <Typography variant="body2" sx={{ mt: 1, color: '#fff' }}>Ingestion Pipeline</Typography>
        </Box>
      </div>
      
      {/* Main Dashboard Area */}
      <Box sx={{ flexGrow: 1, p: 4, overflow: 'auto' }}>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={4}>
          <Typography variant="h4" fontWeight="bold">Pipeline Observability</Typography>
          <Button 
            startIcon={<RefreshIcon />} 
            variant="contained" 
            onClick={() => {
              queryClient.invalidateQueries({ queryKey: ['ingestionStats'] });
              queryClient.invalidateQueries({ queryKey: ['ingestionJobs'] });
            }}
          >
            Refresh
          </Button>
        </Box>

        {/* Stats Row */}
        <Grid container spacing={3} mb={4}>
          <Grid item xs={12} sm={4}>
            <Card>
              <CardContent>
                <Typography color="text.secondary" gutterBottom>Active Workers</Typography>
                <Typography variant="h3">{statsLoading ? <CircularProgress size={24}/> : stats?.active_workers || 0}</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={4}>
            <Card>
              <CardContent>
                <Typography color="text.secondary" gutterBottom>Jobs In Queue / Active</Typography>
                <Typography variant="h3">{statsLoading ? <CircularProgress size={24}/> : `${stats?.queued || 0} / ${stats?.active || 0}`}</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={4}>
            <Card sx={{ bgcolor: stats?.failed > 0 ? '#fff0f0' : 'inherit' }}>
              <CardContent>
                <Typography color="text.secondary" gutterBottom>Failed Jobs</Typography>
                <Typography variant="h3" color={stats?.failed > 0 ? "error" : "textPrimary"}>
                  {statsLoading ? <CircularProgress size={24}/> : stats?.failed || 0}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* Jobs Table */}
        <Typography variant="h5" mb={2}>Recent Tasks</Typography>
        <TableContainer component={Paper}>
          <Table aria-label="jobs table">
            <TableHead sx={{ bgcolor: '#f0f0f0' }}>
              <TableRow>
                <TableCell width="40"></TableCell>
                <TableCell>Job ID</TableCell>
                <TableCell>File</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Progress</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {jobsLoading && (
                <TableRow>
                  <TableCell colSpan={6} align="center" py={4}><CircularProgress /></TableCell>
                </TableRow>
              )}
              {!jobsLoading && jobs?.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} align="center" py={4}>No jobs found in the ingestion queue.</TableCell>
                </TableRow>
              )}
              {!jobsLoading && jobs?.map((job: any) => (
                <Row key={job.id} job={job} onRetry={(id) => retryMutation.mutate(id)} />
              ))}
            </TableBody>
          </Table>
        </TableContainer>

      </Box>
    </Box>
  );
}
