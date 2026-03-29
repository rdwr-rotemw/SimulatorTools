import apiClient from '../client';

export interface CompilationResult {
  success: boolean;
  cmf_path: string | null;
  var_path: string | null;
  version: string;
  stats: Record<string, number>;
  warnings: string[];
  errors: string[];
}

export const compileMibs = async (
  mibZip: File,
  oidsPdf: File,
  outputName?: string,
  numRows?: number,
  cmfOutputDir?: string,
  varOutputDir?: string,
): Promise<CompilationResult> => {
  const formData = new FormData();
  formData.append('mib_zip', mibZip);
  formData.append('oids_pdf', oidsPdf);
  if (outputName) formData.append('output_name', outputName);
  if (numRows) formData.append('num_rows', numRows.toString());
  if (cmfOutputDir) formData.append('cmf_output_dir', cmfOutputDir);
  if (varOutputDir) formData.append('var_output_dir', varOutputDir);

  const response = await apiClient.post<CompilationResult>(
    '/oid-compiler/compile',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 120000 }
  );
  return response.data;
};

export const checkHealth = async (): Promise<{ status: string; module: string }> => {
  const response = await apiClient.get('/oid-compiler/health');
  return response.data;
};
