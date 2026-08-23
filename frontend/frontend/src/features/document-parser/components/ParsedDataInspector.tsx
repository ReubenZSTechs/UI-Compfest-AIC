import { useState } from 'react';
import type {
  ParseJobResult,
  FactoryAsset,
  JobDesk,
  WorkerRecord,
  CompatibilityWorkerRecord,
} from '../types/documentParser.types';
import styles from './ParsedDataInspector.module.css';

interface ParsedDataInspectorProps {
  result: ParseJobResult;
  onProceed: () => void;
}

type TabType = 'overview' | 'factory' | 'workers' | 'compatibility' | 'raw';

export function ParsedDataInspector({ result, onProceed }: ParsedDataInspectorProps) {
  const [activeTab, setActiveTab] = useState<TabType>('overview');

  const factoryStructure = result.factoryStructure;
  const factoryInfo = factoryStructure?.factory_info;

  // Handling fallback array untuk job desks/descriptions, assets, parallel groups, dan workers
  const jobDesks: JobDesk[] =
    factoryStructure?.job_desks ??
    factoryStructure?.job_descriptions ??
    [];
  const assets: FactoryAsset[] = factoryStructure?.assets ?? [];
  const parallelGroups = factoryInfo?.parallel_groups ?? [];
  const workers: WorkerRecord[] = result.workerProfile?.workers ?? [];
  const matrixData = result.compatibilityMatrix;

  // Nama pabrik dari backend
  const factoryDisplayName =
    factoryInfo?.factory_name ||
    factoryInfo?.factory_id ||
    result.factoryId ||
    'Digital Twin Plant';

  // Jumlah job desk & pekerja efektif (fallback jika backend mengembalikan nilai 0)
  const effectiveJobDesksCount = Math.max(result.jobDesksParsed || 0, jobDesks.length);
  const effectiveWorkersCount = Math.max(result.workersParsed || 0, workers.length);

  return (
    <section className={styles.inspectorContainer}>
      <div className={styles.inspectorHeader}>
        <div>
          <span className={styles.badge}>Hasil Output Parsing (Tahap 1 - 5)</span>
          <h2 className={styles.inspectorTitle}>Pratinjau Data Digital Twin</h2>
        </div>
      </div>

      {/* --- METRIC CARDS --- */}
      <div className={styles.metricsRow}>
        <div className={styles.metricCard}>
          <span className={styles.metricLabel}>Pabrik / Fasilitas</span>
          <span className={styles.metricValue}>{factoryDisplayName}</span>
          <span className={styles.metricSub}>ID: {result.factoryId || 'N/A'}</span>
        </div>

        <div className={styles.metricCard}>
          <span className={styles.metricLabel}>Job Desk Teridentifikasi</span>
          <span className={styles.metricValue}>{effectiveJobDesksCount}</span>
          <span className={styles.metricSub}>{assets.length} Aset Terhubung</span>
        </div>

        <div className={styles.metricCard}>
          <span className={styles.metricLabel}>Pekerja Terparsing</span>
          <span className={styles.metricValue}>{effectiveWorkersCount}</span>
          <span className={styles.metricSub}>Profil CV Diekstrak</span>
        </div>

        <div className={styles.metricCard}>
          <span className={styles.metricLabel}>Matriks Kompatibilitas</span>
          <span className={styles.metricValue}>
            {matrixData ? 'Terbentuk' : 'Belum Ada'}
          </span>
          <span className={styles.metricSub}>
            {matrixData?.meta?.evaluated_pairs !== undefined
              ? `${matrixData.meta.evaluated_pairs} Pasangan Dievaluasi`
              : `${result.warnings.length} Peringatan`}
          </span>
        </div>
      </div>

      {/* --- TABS NAVIGATION --- */}
      <div className={styles.tabBar}>
        <button
          type="button"
          className={`${styles.tabButton} ${activeTab === 'overview' ? styles.activeTab : ''}`}
          onClick={() => setActiveTab('overview')}
        >
          Ringkasan
        </button>
        <button
          type="button"
          className={`${styles.tabButton} ${activeTab === 'factory' ? styles.activeTab : ''}`}
          onClick={() => setActiveTab('factory')}
        >
          Struktur Pabrik ({jobDesks.length} Job / {assets.length} Aset)
        </button>
        <button
          type="button"
          className={`${styles.tabButton} ${activeTab === 'workers' ? styles.activeTab : ''}`}
          onClick={() => setActiveTab('workers')}
        >
          Profil Pekerja ({workers.length})
        </button>
        <button
          type="button"
          className={`${styles.tabButton} ${activeTab === 'compatibility' ? styles.activeTab : ''}`}
          onClick={() => setActiveTab('compatibility')}
        >
          Matriks Kompatibilitas
        </button>
        <button
          type="button"
          className={`${styles.tabButton} ${activeTab === 'raw' ? styles.activeTab : ''}`}
          onClick={() => setActiveTab('raw')}
        >
          JSON Mentah
        </button>
      </div>

      {/* --- TAB CONTENT PANELS --- */}
      <div className={styles.tabContent}>
        {/* TAB 1: OVERVIEW */}
        {activeTab === 'overview' && (
          <div className={styles.overviewPanel}>
            <div className={styles.sectionBlock}>
              <h3>Informasi Umum Job & Pabrik</h3>
              <ul className={styles.infoList}>
                <li>
                  <strong>Simulation ID:</strong> <code>{result.simulationId || result.jobId}</code>
                </li>
                <li>
                  <strong>Factory ID:</strong> <code>{result.factoryId ?? 'N/A'}</code>
                </li>
                <li>
                  <strong>Tipe Proses:</strong>{' '}
                  {factoryInfo?.process_type ? factoryInfo.process_type.toUpperCase() : '-'}
                </li>
                <li>
                  <strong>Jumlah Pekerja Terdeklarasi:</strong>{' '}
                  {factoryInfo?.declared_worker_count ?? '-'} Orang
                </li>
                <li>
                  <strong>Deskripsi Tata Letak:</strong> {factoryInfo?.layout_description || '-'}
                </li>
              </ul>
            </div>

            {factoryInfo?.workflow_sequence && (
              <div className={styles.sectionBlock}>
                <h4>Tahapan Alur Kerja (Workflow Sequence)</h4>
                <div className={styles.chipGroup}>
                  {factoryInfo.workflow_sequence.map((step: string, i: number) => (
                    <span key={i} className={styles.skillChip}>{step}</span>
                  ))}
                </div>
              </div>
            )}

            {result.warnings.length > 0 && (
              <div className={styles.warningBox}>
                <h4>Catatan & Peringatan Parser ({result.warnings.length})</h4>
                <ul>
                  {result.warnings.map((warn, i) => (
                    <li key={`${warn}-${i}`}>{warn}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: PABRIK, ASET & JOB DESK */}
        {activeTab === 'factory' && (
          <div className={styles.factoryPanel}>
            {/* Sub-bagian 1: Informasi Tata Letak & Grup Paralel */}
            <div className={styles.sectionBlock}>
              <h3>Tata Letak Pabrik & Alur Paralel</h3>
              <p>{factoryInfo?.layout_description || 'Tidak ada deskripsi tata letak.'}</p>

              {parallelGroups.length > 0 && (
                <div className={styles.sectionBlock}>
                  <h4>Grup Proses Paralel ({parallelGroups.length})</h4>
                  <ul className={styles.infoList}>
                    {parallelGroups.map((grp, i) => (
                      <li key={grp.group_id || i}>
                        <strong>{grp.group_id}:</strong> Tahap <code>{grp.steps?.join(', ')}</code>
                        <br />
                        <small className={styles.mutedText}>{grp.reasoning}</small>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* Sub-bagian 2: Daftar Aset / Mesin */}
            <div className={styles.sectionBlock}>
              <h3>Daftar Aset & Mesin Produksi ({assets.length})</h3>
              {assets.length === 0 ? (
                <p className={styles.emptyText}>Tidak ada data aset terurai.</p>
              ) : (
                <table className={styles.dataTable}>
                  <thead>
                    <tr>
                      <th>ID Aset / Nama</th>
                      <th>Kategori</th>
                      <th>Tahap Workflow</th>
                      <th>Status Otomasi</th>
                      <th>Kapasitas Utama</th>
                      <th>Biaya / Jam</th>
                      <th>Faktor Lingkungan</th>
                    </tr>
                  </thead>
                  <tbody>
                    {assets.map((ast, idx) => (
                      <tr key={ast.asset_id || idx}>
                        <td>
                          <strong>{ast.asset_name}</strong>
                          <br />
                          <small className={styles.mutedText}>{ast.asset_id}</small>
                        </td>
                        <td>{ast.category || '-'}</td>
                        <td><code>{ast.workflow_step || '-'}</code></td>
                        <td>
                          <span className={styles.skillChip}>
                            {ast.is_automated ? 'Otomatis (Automated)' : 'Manual'}
                          </span>
                        </td>
                        <td>
                          <strong>{ast.base_throughput_capacity ?? '-'}</strong> Pcs/Jam ({ast.units_available ?? 1} Unit)
                        </td>
                        <td>${ast.operational_cost_per_hour ?? 0}/Jam</td>
                        <td>
                          {ast.environmental_factors ? (
                            <small>
                              Kebisingan: <strong>{ast.environmental_factors.noise_level_db ?? '-'} dB</strong> |{' '}
                              Getaran: <strong>{ast.environmental_factors.vibration_hazard_level ?? '-'}</strong>
                            </small>
                          ) : (
                            '-'
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            {/* Sub-bagian 3: Daftar Job Description */}
            <div className={styles.sectionBlock}>
              <h3>Daftar Job Description & Tuntutan Kerja ({jobDesks.length})</h3>
              {jobDesks.length === 0 ? (
                <p className={styles.emptyText}>Tidak ada data job desk terurai.</p>
              ) : (
                <table className={styles.dataTable}>
                  <thead>
                    <tr>
                      <th>Job ID / Judul</th>
                      <th>Tahap Alur Kerja</th>
                      <th>Aset Terkait</th>
                      <th>Tuntutan Kerja (Demands)</th>
                      <th>Persyaratan QC</th>
                    </tr>
                  </thead>
                  <tbody>
                    {jobDesks.map((jd, idx) => (
                      <tr key={jd.job_id || idx}>
                        <td>
                          <strong>{jd.job_title || jd.job_id}</strong>
                          <br />
                          <small className={styles.mutedText}>{jd.job_id}</small>
                        </td>
                        <td><code>{jd.workflow_step || '-'}</code></td>
                        <td><code>{jd.assigned_asset_id || '-'}</code></td>
                        <td>
                          {jd.demands ? (
                            <small>
                              Fisik: <strong>{jd.demands.physical_demand_level ?? '-'}</strong> |{' '}
                              Fokus: <strong>{jd.demands.required_cognitive_focus ?? '-'}</strong> |{' '}
                              Kompleksitas: <strong>{jd.demands.task_complexity ?? '-'}</strong>
                            </small>
                          ) : (
                            '-'
                          )}
                        </td>
                        <td>{jd.qc_requirement || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}

        {/* TAB 3: PROFIL PEKERJA */}
        {activeTab === 'workers' && (
          <div className={styles.workersPanel}>
            <h3>Daftar Karyawan Ter-parsing dari CV</h3>
            {workers.length === 0 ? (
              <p className={styles.emptyText}>Tidak ada data pekerja terurai.</p>
            ) : (
              <div className={styles.workersGrid}>
                {workers.map((w, idx) => {
                  const demo = w.demographics || {};
                  const shift = w.shift_context || {};
                  const expYears = demo.years_of_experience ?? 0;
                  const skillsList: string[] = w.skills ?? w.certifications ?? w.capabilities ?? [];

                  return (
                    <div key={w.worker_id || idx} className={styles.workerCard}>
                      <div className={styles.workerHeader}>
                        <span className={styles.workerAvatar}>
                          {(w.name || 'W')[0].toUpperCase()}
                        </span>
                        <div>
                          <h4 className={styles.workerName}>{w.name || w.worker_id}</h4>
                          <span className={styles.workerRole}>ID: {w.worker_id}</span>
                        </div>
                      </div>
                      <div className={styles.workerBody}>
                        <p><strong>Pengalaman:</strong> {expYears} Tahun</p>
                        <p><strong>Demografi:</strong> Usia {demo.age ?? '-'} Thn | Gender: {demo.gender ?? '-'}</p>
                        <p><strong>Shift Hari Ini:</strong> {shift.hours_worked_today ?? 0} Jam (Shift Berturut: {shift.consecutive_shifts ?? 0})</p>

                        <div style={{ marginTop: '0.5rem' }}>
                          <p style={{ margin: '0 0 0.25rem 0', fontSize: '0.75rem', fontWeight: 600 }}>Metrik Fisiologis:</p>
                          <div className={styles.chipGroup}>
                            {demo.baseline_physical_stamina !== undefined && (
                              <span className={styles.skillChip}>
                                Stamina: {(demo.baseline_physical_stamina * 100).toFixed(0)}%
                              </span>
                            )}
                            {demo.cognitive_resilience !== undefined && (
                              <span className={styles.skillChip}>
                                Resiliensi: {(demo.cognitive_resilience * 100).toFixed(0)}%
                              </span>
                            )}
                          </div>
                        </div>

                        {skillsList.length > 0 && (
                          <div style={{ marginTop: '0.5rem' }}>
                            <p style={{ margin: '0 0 0.25rem 0', fontSize: '0.75rem', fontWeight: 600 }}>Keterampilan & Sertifikasi:</p>
                            <div className={styles.chipGroup}>
                              {skillsList.map((sk, sIdx) => (
                                <span key={sIdx} className={styles.skillChip}>{sk}</span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* TAB 4: MATRIKS KOMPATIBILITAS */}
        {activeTab === 'compatibility' && (
          <div className={styles.matrixPanel}>
            <h3>Evaluasi Kesesuaian Pekerja & Job Desk</h3>
            {!matrixData ? (
              <p className={styles.emptyText}>Matriks kompatibilitas tidak tersedia.</p>
            ) : (
              <div>
                {matrixData.meta && (
                  <div className={styles.sectionBlock}>
                    <p>
                      <strong>Total Pasangan Dievaluasi:</strong> {matrixData.meta.evaluated_pairs ?? 0} |{' '}
                      <strong>Jumlah Pekerja:</strong> {matrixData.meta.worker_count ?? 0} |{' '}
                      <strong>Jumlah Pekerjaan:</strong> {matrixData.meta.job_count ?? 0}
                    </p>
                  </div>
                )}

                {matrixData.compatibility_matrix ? (
                  <table className={styles.dataTable}>
                    <thead>
                      <tr>
                        <th>Nama Pekerja</th>
                        <th>Job Match Terbaik</th>
                        <th>Skor Kesesuaian</th>
                        <th>Multiplier Throughput</th>
                        <th>Multiplier Error</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(matrixData.compatibility_matrix).map(([wrkId, item]: [string, CompatibilityWorkerRecord]) => {
                        const bestJobId = item.best_job_id;
                        const bestJobEval = bestJobId ? item.jobs?.[bestJobId]?.evaluations : undefined;
                        return (
                          <tr key={wrkId}>
                            <td>
                              <strong>{item.worker_name || wrkId}</strong>
                              <br />
                              <small className={styles.mutedText}>{wrkId}</small>
                            </td>
                            <td>
                              <code>{bestJobId || '-'}</code>
                              <br />
                              <small>{bestJobId ? item.jobs?.[bestJobId]?.job_title || '-' : '-'}</small>
                            </td>
                            <td>
                              <strong>
                                {bestJobEval?.overall_compatibility_score !== undefined
                                  ? `${(bestJobEval.overall_compatibility_score * 100).toFixed(0)}%`
                                  : '-'}
                              </strong>
                            </td>
                            <td>{bestJobEval?.throughput_multiplier ?? '-'}x</td>
                            <td>{bestJobEval?.error_multiplier ?? '-'}x</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                ) : (
                  <pre className={styles.codeBlock}>
                    {JSON.stringify(matrixData, null, 2)}
                  </pre>
                )}
              </div>
            )}
          </div>
        )}

        {/* TAB 5: JSON MENTAH */}
        {activeTab === 'raw' && (
          <div className={styles.rawPanel}>
            <pre className={styles.codeBlock}>
              {JSON.stringify(result, null, 2)}
            </pre>
          </div>
        )}
      </div>

      {/* --- ACTION BAR MENUJU HALAMAN DIGITAL TWIN --- */}
      <div className={styles.inspectorFooter}>
        <p className={styles.footerHint}>
          Periksa kelengkapan data di atas. Klik tombol di bawah jika Anda siap melanjutkan.
        </p>
        <button type="button" className={styles.proceedButton} onClick={onProceed}>
          Sudah Dicek, Buka Digital Twin Dashboard →
        </button>
      </div>
    </section>
  );
}