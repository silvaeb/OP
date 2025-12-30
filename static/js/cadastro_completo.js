// JavaScript completo para cadastro aprimorado - VERSÃO COM TRATAMENTO DE ERROS

// Variáveis globais (não redeclarar se já existem em outro script)
if (typeof instalacaoCount === 'undefined') instalacaoCount = 0;
if (typeof viaturaCount === 'undefined') viaturaCount = 0;
if (typeof pessoalCount === 'undefined') pessoalCount = 0;
if (typeof geradorCount === 'undefined') geradorCount = 0;
if (typeof empilhadeiraCounts === 'undefined') empilhadeiraCounts = {};
if (typeof sistemaCounts === 'undefined') sistemaCounts = {};
if (typeof equipamentoCounts === 'undefined') equipamentoCounts = {};
if (typeof omsSelecionadas === 'undefined') window.omsSelecionadas = [];

// Inicializar quando o DOM estiver carregado
document.addEventListener('DOMContentLoaded', function() {
    console.log('Sistema de cadastro completo carregado');
    
    // Verificar se os containers existem
    verificarContainers();
    
    // Configurar botões
    setupButtons();

    // Ajustar exibição dos campos de Classe I conforme seleção
    try { setupClasseIVisibility(); } catch (e) { console.warn('Falha ao configurar visibilidade de Classe I', e); }

    // Pré-preencher dados no modo edição
    if (window.EDIT_MODE && window.PRELOAD_ORGAO) {
        preencherDadosEdicao(window.PRELOAD_ORGAO);
        preencherOutrasAbas(window.PRELOAD_DATA || {});
        // Garantir reconstrução das OMs selecionadas após DOM pronto
        if (typeof preCarregarOMsSelecionadas === 'function') {
            preCarregarOMsSelecionadas();
        }
        // Recalcular suprimentos se efetivo vier preenchido
        try { calcularSuprimentoAutomatico(); } catch (e) { console.warn('Erro ao recalcular suprimento na edição', e); }
    }
    
    console.log("✓ Sistema de cadastro inicializado com sucesso!");
});

// Preenche campos principais quando em modo edição
function preencherDadosEdicao(data) {
    try {
        const setValue = (id, value) => {
            const el = document.getElementById(id);
            if (el) {
                el.value = value ?? '';
            }
        };

        const form = document.getElementById('cadastroForm');

        const nomeSelect = document.getElementById('nome');
        if (nomeSelect) {
            nomeSelect.value = data.nome || '';
            nomeSelect.disabled = true; // manter consistência, evitando troca de OP
            if (form) {
                const hiddenNome = document.createElement('input');
                hiddenNome.type = 'hidden';
                hiddenNome.name = 'nome';
                hiddenNome.value = data.nome || '';
                form.appendChild(hiddenNome);
            }
        }

        setValue('sigla', data.sigla);
        const siglaInput = document.getElementById('sigla');
        if (siglaInput) siglaInput.readOnly = true;

        setValue('unidade_gestora', data.unidade_gestora);
        setValue('codom', data.codom);
        setValue('om_licitacao_qs', data.om_licitacao_qs);
        setValue('om_licitacao_qr', data.om_licitacao_qr);
        setValue('subordinacao', data.subordinacao);
        setValue('data_criacao', data.data_criacao);
        setValue('missao', data.missao);

        // OMs apoiadas (mantém compatibilidade: string separada por vírgula)
        const omsHidden = document.getElementById('oms_que_apoia_selected');
        if (omsHidden) {
            omsHidden.value = data.historico || '';
        }
        const omsSelecionadas = document.getElementById('oms_selecionadas');
        if (omsSelecionadas) {
            omsSelecionadas.value = data.historico || '';
        }

        // Popular tabela de OMs selecionadas (com funções definidas no template)
        if (typeof preencherOMsSelecionadas === 'function') {
            preencherOMsSelecionadas(data.historico || '');
        }

        setValue('efetivo', data.efetivo_atendimento);
        setValue('consumo_secos', data.consumo_secos_mensal);
        setValue('consumo_frigorificados', data.consumo_frigorificados_mensal);
        setValue('suprimento_secos', data.suprimento_secos_mensal);
        setValue('suprimento_frigorificados', data.suprimento_frigorificados_mensal);
        setValue('capacidade_total_toneladas', data.capacidade_total_toneladas);
        setValue('capacidade_total_toneladas_seco', data.capacidade_total_toneladas_seco);
        setValue('area_edificavel', data.area_edificavel_disponivel);

        // Manter abas utilizáveis no modo edição, mas retirar obrigações de campos ainda não preenchidos
        ['energia-geradores','pessoal','viaturas','instalacoes'].forEach(function(tabId) {
            const tab = document.getElementById(tabId);
            if (tab) {
                tab.querySelectorAll('input, select, textarea').forEach(function(el) {
                    el.removeAttribute('required');
                });
            }
        });

    } catch (err) {
        console.error('Erro ao preencher dados de edição:', err);
    }
}

// Preenche demais abas com dados existentes
function preencherOutrasAbas(data) {
    try {
        if (!data) return;
        preencherEnergia(data.energia);
        preencherGeradores(data.geradores);
        preencherPessoal(data.pessoal);
        preencherViaturas(data.viaturas);
        preencherInstalacoes(data.instalacoes);
    } catch (err) {
        console.error('Erro ao preencher demais abas:', err);
    }
}

function preencherEnergia(energia) {
    if (!energia) return;
    setFieldValue('dimensionamento_energia', energia.dimensionamento_adequado);
    setFieldValue('capacidade_total_kva', energia.capacidade_total_kva);
    setFieldValue('observacoes_energia', energia.observacoes_energia);
}

function preencherGeradores(lista) {
    if (!Array.isArray(lista)) return;
    lista.forEach(function(g) {
        const idx = geradorCount;
        addGerador();
        setFieldValue(`gerador_capacidade_${idx}`, g.capacidade_kva);
        setFieldValue(`gerador_marca_${idx}`, g.marca_modelo);
        setFieldValue(`gerador_ano_${idx}`, g.ano_fabricacao);
        const chk24h = document.querySelector(`[name="gerador_24h_${idx}"]`);
        if (chk24h) chk24h.checked = !!g.pode_operar_24h;
        setFieldValue(`gerador_situacao_${idx}`, g.situacao);
        setFieldValue(`gerador_valor_recuperacao_${idx}`, g.valor_recuperacao);
        setFieldValue(`gerador_horas_${idx}`, g.horas_operacao_continuas);
        setFieldValue(`gerador_ultima_manutencao_${idx}`, g.ultima_manutencao);
        setFieldValue(`gerador_proxima_manutencao_${idx}`, g.proxima_manutencao);
        setFieldValue(`gerador_observacoes_${idx}`, g.observacoes);
        // Exibir campo valor de recuperação se necessário
        const situacaoSelect = document.getElementById(`gerador_situacao_${idx}`);
        if (situacaoSelect) {
            handleSituacaoChange(situacaoSelect, idx, 'gerador');
        }

        // Fotos existentes (preload)
        if (Array.isArray(g.fotos) && g.fotos.length > 0 && typeof renderExistingPhotos === 'function') {
            renderExistingPhotos(`geradorPreview${idx}`, g.fotos);
        }
    });
}

function preencherPessoal(lista) {
    if (!Array.isArray(lista)) return;
    lista.forEach(function(p) {
        const idx = pessoalCount;
        addPessoal();
        setFieldValue(`pessoal_posto_${idx}`, p.posto_graduacao);
        setFieldValue(`pessoal_arma_${idx}`, p.arma_quadro_servico);
        setFieldValue(`pessoal_especialidade_${idx}`, p.especialidade);
        setFieldValue(`pessoal_funcao_${idx}`, p.funcao);
        setFieldValue(`pessoal_tipo_${idx}`, p.tipo_servico);
        setFieldValue(`pessoal_quantidade_${idx}`, p.quantidade);
        setFieldValue(`pessoal_observacoes_${idx}`, p.observacoes);
    });
}

function preencherViaturas(lista) {
    if (!Array.isArray(lista)) return;
    lista.forEach(function(v) {
        const idx = viaturaCount;
        addViatura();
        setFieldValue(`viatura_tipo_${idx}`, v.tipo_veiculo);
        setFieldValue(`viatura_especializacao_${idx}`, v.especializacao);
        setFieldValue(`viatura_eb_${idx}`, v.placa); // placa armazena EB
        setFieldValue(`viatura_marca_${idx}`, v.marca);
        setFieldValue(`viatura_modelo_${idx}`, v.modelo);
        setFieldValue(`viatura_ano_${idx}`, v.ano_fabricacao);
        setFieldValue(`viatura_capacidade_${idx}`, v.capacidade_carga_kg);
        setFieldValue(`viatura_lotacao_${idx}`, v.lotacao_pessoas);
        setFieldValue(`viatura_situacao_${idx}`, v.situacao);
        setFieldValue(`viatura_valor_recuperacao_${idx}`, v.valor_recuperacao);
        setFieldValue(`viatura_km_${idx}`, v.km_atual);
        setFieldValue(`viatura_ultima_manutencao_${idx}`, v.ultima_manutencao);
        setFieldValue(`viatura_proxima_manutencao_${idx}`, v.proxima_manutencao);
        setFieldValue(`viatura_patrimonio_${idx}`, v.patrimonio);
        setFieldValue(`viatura_observacoes_${idx}`, v.observacoes);

        // Fotos existentes (preload)
        if (Array.isArray(v.fotos) && v.fotos.length > 0 && typeof renderExistingPhotos === 'function') {
            renderExistingPhotos(`viaturaPreview${idx}`, v.fotos);
        }
    });
}

function preencherInstalacoes(lista) {
    if (!Array.isArray(lista)) return;
    lista.forEach(function(inst) {
        const idx = instalacaoCount;
        addInstalacao(true); // evitar alerta ao carregar dados existentes
        setFieldValue(`tipo_instalacao_${idx}`, inst.tipo_instalacao);
        setFieldValue(`instalacao_nome_${idx}`, inst.nome_identificacao || '');
        setFieldValue(`descricao_${idx}`, inst.descricao);
        setFieldValue(`data_construcao_${idx}`, inst.data_construcao);
        setFieldValue(`tipo_cobertura_${idx}`, inst.tipo_cobertura);
        setFieldValue(`capacidade_${idx}`, inst.capacidade_toneladas);
        setFieldValue(`largura_${idx}`, inst.largura);
        setFieldValue(`comprimento_${idx}`, inst.comprimento);
        setFieldValue(`altura_${idx}`, inst.altura);
        setFieldValue(`verticalizacao_${idx}`, inst.verticalizacao);

        // Fotos da instalação
        if (Array.isArray(inst.fotos) && inst.fotos.length > 0 && typeof renderExistingPhotos === 'function') {
            renderExistingPhotos(`instalacaoPreview${idx}`, inst.fotos);
        }

        // Empilhadeiras
        if (Array.isArray(inst.empilhadeiras)) {
            inst.empilhadeiras.forEach(function(emp) {
                addEmpilhadeira(idx);
                const empIdx = empilhadeiraCounts[idx] - 1; // addEmpilhadeira incrementa
                setFieldValue(`empilhadeira_tipo_${idx}_${empIdx}`, emp.tipo);
                setFieldValue(`empilhadeira_capacidade_${idx}_${empIdx}`, emp.capacidade);
                setFieldValue(`empilhadeira_quantidade_${idx}_${empIdx}`, emp.quantidade);
                setFieldValue(`empilhadeira_ano_${idx}_${empIdx}`, emp.ano_fabricacao);
                setFieldValue(`empilhadeira_situacao_${idx}_${empIdx}`, emp.situacao);
                setFieldValue(`empilhadeira_valor_recuperacao_${idx}_${empIdx}`, emp.valor_recuperacao);

                if (Array.isArray(emp.fotos) && emp.fotos.length > 0 && typeof renderExistingPhotos === 'function') {
                    renderExistingPhotos(`empilhadeiraPreview${idx}_${empIdx}`, emp.fotos);
                }
            });
        }

        // Sistemas de segurança
        if (Array.isArray(inst.sistemas)) {
            inst.sistemas.forEach(function(sis) {
                addSistemaSeguranca(idx);
                const sisIdx = sistemaCounts[idx] - 1;
                setFieldValue(`sistema_tipo_${idx}_${sisIdx}`, sis.tipo);
                setFieldValue(`sistema_descricao_${idx}_${sisIdx}`, sis.descricao);
                setFieldValue(`sistema_situacao_${idx}_${sisIdx}`, sis.situacao);
                setFieldValue(`sistema_ultima_manutencao_${idx}_${sisIdx}`, sis.ultima_manutencao);
                setFieldValue(`sistema_proxima_manutencao_${idx}_${sisIdx}`, sis.proxima_manutencao);
            });
        }

        // Equipamentos de unitização
        if (Array.isArray(inst.equipamentos)) {
            inst.equipamentos.forEach(function(eq) {
                addEquipamentoUnitizacao(idx);
                const eqIdx = equipamentoCounts[idx] - 1;
                setFieldValue(`equipamento_tipo_${idx}_${eqIdx}`, eq.tipo);
                setFieldValue(`equipamento_quantidade_${idx}_${eqIdx}`, eq.quantidade);
                setFieldValue(`equipamento_capacidade_${idx}_${eqIdx}`, eq.capacidade_kg);
                setFieldValue(`equipamento_situacao_${idx}_${eqIdx}`, eq.situacao);
                setFieldValue(`equipamento_observacoes_${idx}_${eqIdx}`, eq.observacoes);

                if (Array.isArray(eq.fotos) && eq.fotos.length > 0 && typeof renderExistingPhotos === 'function') {
                    renderExistingPhotos(`equipamentoPreview${idx}_${eqIdx}`, eq.fotos);
                }
            });
        }
    });
}

// Utilitário simples para setar valor por id
function setFieldValue(idOrName, value) {
    let el = document.getElementById(idOrName);
    if (!el) {
        el = document.querySelector(`[name="${idOrName}"]`);
    }
    if (el) {
        el.value = value ?? '';
        const nameAttr = el.getAttribute('name') || '';
        // Disparar eventos para atualizar rótulos ou lógica dependente
        if (nameAttr.startsWith('viatura_eb_')) {
            el.dispatchEvent(new Event('input', { bubbles: true }));
        }
        if (nameAttr.startsWith('viatura_tipo_')) {
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }
        if (nameAttr.startsWith('tipo_instalacao_')) {
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }
        if (nameAttr.startsWith('equipamento_tipo_')) {
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }
}

// Toggle collapse/expand of a card or sub-item
function toggleCard(btn) {
    try {
        const container = btn.closest('.card, .sub-item');
        if (!container) return;
        const body = container.querySelector('.collapsible-body');
        if (!body) return;
        const isCollapsed = body.classList.toggle('collapsed');
        body.style.display = isCollapsed ? 'none' : '';
        const icon = btn.querySelector('.toggle-icon');
        if (icon) icon.textContent = isCollapsed ? '+' : '−';
        btn.setAttribute('aria-expanded', isCollapsed ? 'false' : 'true');
    } catch (err) {
        console.error('Erro ao alternar colapso:', err);
    }
}

// Verificar se os containers existem
function verificarContainers() {
    const containers = [
        'instalacoesContainer',
        'viaturasContainer',
        'pessoalContainer',
        'geradoresContainer'
    ];
    
    containers.forEach(containerId => {
        const container = document.getElementById(containerId);
        if (!container) {
            // Pessoal usa matriz, então ausência do pessoalContainer é esperada no layout atual
            if (containerId === 'pessoalContainer') {
                console.log('ℹ️ Layout usa matriz de pessoal; container de cards não está presente.');
            } else {
                console.error(`Container ${containerId} não encontrado`);
            }
        } else {
            console.log(`✓ Container ${containerId} encontrado`);
        }
    });
}

// Configurar botões do formulário
function setupButtons() {
    // Botão de adicionar instalação
    const addInstalacaoBtn = document.querySelector('[onclick="addInstalacao()"]');
    if (addInstalacaoBtn) {
        addInstalacaoBtn.onclick = addInstalacao;
        console.log('✓ Botão de instalação configurado');
    } else {
        console.error('✗ Botão de instalação não encontrado');
    }
    
    // Botão de adicionar viatura (procura por onclick ou data-action)
    const addViaturaBtn = document.querySelector('[onclick="addViatura()"], [data-action="add-viatura"]');
    if (addViaturaBtn) {
        addViaturaBtn.onclick = addViatura;
        console.log('✓ Botão de viatura configurado');
    } else {
        console.error('✗ Botão de viatura não encontrado');
    }
    
    // Botão de adicionar pessoal
    const addPessoalBtn = document.querySelector('[onclick="addPessoal()"], [data-action="add-pessoal"]');
    if (addPessoalBtn) {
        addPessoalBtn.onclick = addPessoal;
        console.log('✓ Botão de pessoal configurado');
    } else {
        console.error('✗ Botão de pessoal não encontrado');
    }
    
    // Botão de adicionar gerador
    const addGeradorBtn = document.querySelector('[onclick="addGerador()"], [data-action="add-gerador"]');
    if (addGeradorBtn) {
        addGeradorBtn.onclick = addGerador;
        console.log('✓ Botão de gerador configurado');
    } else {
        console.error('✗ Botão de gerador não encontrado');
    }

    // Fallback por delegação: atende buttons com data-action mesmo se não forem encontrados diretamente
    document.addEventListener('click', function(e) {
        try {
            const targetGen = e.target.closest('[data-action="add-gerador"]');
            if (targetGen) {
                e.preventDefault();
                addGerador();
                return;
            }

            const targetPessoal = e.target.closest('[data-action="add-pessoal"]');
            if (targetPessoal) {
                e.preventDefault();
                addPessoal();
                return;
            }

            const targetViatura = e.target.closest('[data-action="add-viatura"]');
            if (targetViatura) {
                e.preventDefault();
                addViatura();
                return;
            }
        } catch (err) {
            console.error('Erro no listener de delegação para add buttons:', err);
        }
    });
}

// Exibe ou oculta os campos de Classe I (efetivo/consumo) conforme checkbox "Classe I"
function setupClasseIVisibility() {
    const classeInputs = Array.from(document.querySelectorAll('input[name="classes_provedor"]'));
    if (!classeInputs.length) return;

    const hasClasseI = () => classeInputs.some(cb => cb.checked && cb.value.toLowerCase().includes('classe i'));
    const target = document.getElementById('classeIFields');
    const syncedInputs = target ? target.querySelectorAll('input') : [];

    const sync = () => {
        const enabled = hasClasseI();
        if (target) target.classList.toggle('d-none', !enabled);
        syncedInputs.forEach(inp => {
            if (inp.id === 'efetivo') {
                inp.required = enabled;
            }
            if (!enabled && inp.type === 'number') {
                inp.value = '';
            }
        });
    };

    classeInputs.forEach(cb => cb.addEventListener('change', sync));
    sync();
}

// ==================== FUNÇÕES DE INSTALAÇÃO (CORRIGIDAS) ====================

function addInstalacao(silent = false) {
    try {
        console.log('Adicionando instalação ' + instalacaoCount);
        const currentIndex = instalacaoCount;
        
        const container = document.getElementById('instalacoesContainer');
        if (!container) {
            alert('Container de instalações não encontrado');
            return;
        }
        
        const template = document.getElementById('instalacaoTemplate');
        if (!template) {
            alert('Template de instalação não encontrado');
            return;
        }
        
        const clone = template.content.cloneNode(true);
        const instalacaoDiv = clone.querySelector('.instalacao-card');
        
        if (!instalacaoDiv) {
            alert('Elemento .instalacao-card não encontrado no template');
            return;
        }
        
        // Atualizar índice
        instalacaoDiv.dataset.index = currentIndex;
        
        // Atualizar número visível
        const numeroSpan = instalacaoDiv.querySelector('.instalacao-numero');
        if (numeroSpan) {
            numeroSpan.textContent = currentIndex + 1;
        }
        
        // Atualizar todos os IDs e names
        updateInstalacaoIdsAndNames(instalacaoDiv, currentIndex);
        
        // Configurar o select de tipo de instalação
        const tipoSelect = instalacaoDiv.querySelector('select[name^="tipo_instalacao_"]');
        if (tipoSelect) {
            // Remover qualquer atributo onchange existente
            tipoSelect.removeAttribute('onchange');
            
            // Adicionar novo event listener
            tipoSelect.addEventListener('change', function() {
                console.log('Select de tipo alterado:', this.value, 'instalacaoIndex:', currentIndex);
                toggleDepositoSubsecoes(this, currentIndex);
            });
        }
        
        // Configurar botões
        const empBtn = instalacaoDiv.querySelector('button[onclick^="addEmpilhadeira"]');
        if (empBtn) {
            empBtn.setAttribute('onclick', `addEmpilhadeira(${currentIndex})`);
        }
        
        const sisBtn = instalacaoDiv.querySelector('button[onclick^="addSistemaSeguranca"]');
        if (sisBtn) {
            sisBtn.setAttribute('onclick', `addSistemaSeguranca(${currentIndex})`);
        }
        
        const eqBtn = instalacaoDiv.querySelector('button[onclick^="addEquipamentoUnitizacao"]');
        if (eqBtn) {
            eqBtn.setAttribute('onclick', `addEquipamentoUnitizacao(${currentIndex})`);
        }
        
        const removeBtn = instalacaoDiv.querySelector('button[onclick="removeInstalacao(this)"]');
        if (removeBtn) {
            removeBtn.onclick = function() { removeInstalacao(this); };
        }
        
        // Adicionar ao container
        container.appendChild(clone);
        
        // Inicializar contadores para sub-itens
        empilhadeiraCounts[currentIndex] = 0;
        sistemaCounts[currentIndex] = 0;
        equipamentoCounts[currentIndex] = 0;
        
        // Atualizar contador no formulário
        const countInput = document.getElementById('instalacoes_count');
        if (countInput) {
            countInput.value = instalacaoCount + 1;
        }
        
        instalacaoCount++;
        
        if (!silent) {
            showAlert('Instalação adicionada com sucesso', 'success');
        }
        
    } catch (error) {
        console.error('Erro ao adicionar instalação:', error);
        alert('Erro ao adicionar instalação: ' + error.message);
    }
}

function updateInstalacaoIdsAndNames(element, index) {
    try {
        const rewriteFirstIndex = (val) => {
            if (!val) return val;
            // Caso IDs terminem com número (ex: empilhadeirasContainer0, instalacaoPreview0)
            if (/\d+$/.test(val) && !val.includes('_')) {
                return val.replace(/\d+$/, `${index}`);
            }
            // Para atributos com padrão prefix_idx[_subidx]
            if (/_\d+/.test(val)) {
                return val.replace(/_(\d+)/, `_${index}`);
            }
            return val;
        };

        element.querySelectorAll('[name], [id], label[for]').forEach(el => {
            if (el.name) {
                el.name = rewriteFirstIndex(el.name);
            }
            if (el.id) {
                el.id = rewriteFirstIndex(el.id);
            }
            if (el.tagName === 'LABEL' && el.htmlFor) {
                el.htmlFor = rewriteFirstIndex(el.htmlFor);
            }
        });

        // Ajustar onclick dos botões principais de sub-itens
        const empBtn = element.querySelector('button[onclick^="addEmpilhadeira("]');
        if (empBtn) empBtn.setAttribute('onclick', `addEmpilhadeira(${index})`);
        const sisBtn = element.querySelector('button[onclick^="addSistemaSeguranca("]');
        if (sisBtn) sisBtn.setAttribute('onclick', `addSistemaSeguranca(${index})`);
        const eqBtn = element.querySelector('button[onclick^="addEquipamentoUnitizacao("]');
        if (eqBtn) eqBtn.setAttribute('onclick', `addEquipamentoUnitizacao(${index})`);

        // Atualizar change do input de fotos da instalação
        const instFoto = element.querySelector('input[id^="instalacao_fotos_"]');
        const instPreview = element.querySelector('[id^="instalacaoPreview"]');
        if (instFoto) {
            if (instFoto.id) instFoto.id = rewriteFirstIndex(instFoto.id);
            if (instFoto.name) instFoto.name = rewriteFirstIndex(instFoto.name);
            const previewId = instPreview ? instPreview.id : `instalacaoPreview${index}`;
            instFoto.setAttribute('onchange', `previewImage(this, '${previewId}')`);
        }
        if (instPreview && instPreview.id) instPreview.id = rewriteFirstIndex(instPreview.id);

        // Ajustar IDs específicos de containers de sub-itens e contadores
        const empContainer = element.querySelector('[id^="empilhadeirasContainer"]');
        if (empContainer) empContainer.id = `empilhadeirasContainer${index}`;
        const sisContainer = element.querySelector('[id^="sistemasContainer"]');
        if (sisContainer) sisContainer.id = `sistemasContainer${index}`;
        const eqContainer = element.querySelector('[id^="equipamentosContainer"]');
        if (eqContainer) eqContainer.id = `equipamentosContainer${index}`;

        const empCount = element.querySelector('[name^="empilhadeiras_count_"]');
        if (empCount) {
            empCount.name = `empilhadeiras_count_${index}`;
            empCount.id = `empilhadeiras_count_${index}`;
        }
        const sisCount = element.querySelector('[name^="sistemas_count_"]');
        if (sisCount) {
            sisCount.name = `sistemas_count_${index}`;
            sisCount.id = `sistemas_count_${index}`;
        }
        const eqCount = element.querySelector('[name^="equipamentos_count_"]');
        if (eqCount) {
            eqCount.name = `equipamentos_count_${index}`;
            eqCount.id = `equipamentos_count_${index}`;
        }
    } catch (error) {
        console.error('Erro ao atualizar IDs da instalação:', error);
    }
}

// ==================== FUNÇÕES DE GERADOR (CORRIGIDAS) ====================

function addGerador() {
    try {
        console.log('Adicionando gerador ' + geradorCount);
        
        const container = document.getElementById('geradoresContainer');
        if (!container) {
            alert('Container de geradores não encontrado');
            return;
        }
        
        const template = document.getElementById('geradorTemplate');
        if (!template) {
            alert('Template de gerador não encontrado');
            return;
        }
        
        const clone = template.content.cloneNode(true);
        const geradorDiv = clone.querySelector('.gerador-card');
        
        if (!geradorDiv) {
            alert('Elemento .gerador-card não encontrado no template');
            return;
        }
        
        // Atualizar índice
        geradorDiv.dataset.geradorIndex = geradorCount;
        
        // Atualizar número visível
        const numeroSpan = geradorDiv.querySelector('.gerador-numero');
        if (numeroSpan) {
            numeroSpan.textContent = geradorCount + 1;
        }
        
        // Atualizar todos os names e IDs
        updateGeradorNames(geradorDiv, geradorCount);
        
        // Atualizar event handler de remoção
        const removeBtn = geradorDiv.querySelector('[onclick="removeGerador(this)"]');
        if (removeBtn) {
            removeBtn.onclick = function() { removeGerador(this); };
        }
        
        container.appendChild(clone);
        
        // Garantir visibilidade do campo valor_recuperacao conforme situação inicial
        const situacaoSelectInit = geradorDiv.querySelector('select[name^="gerador_situacao_"]');
        if (situacaoSelectInit) {
            handleSituacaoChange(situacaoSelectInit, geradorCount, 'gerador');
        }

        // Atualizar contador no formulário
        const countInput = document.getElementById('geradores_count');
        if (countInput) {
            countInput.value = geradorCount + 1;
        }
        
        geradorCount++;
        
        showAlert('Gerador adicionado com sucesso', 'success');
        
    } catch (error) {
        console.error('Erro ao adicionar gerador:', error);
        alert('Erro ao adicionar gerador: ' + error.message);
    }
}

function updateGeradorNames(element, index) {
    try {
        const elementsWithName = element.querySelectorAll('[name]');
        elementsWithName.forEach(el => {
            const name = el.getAttribute('name');
            if (name && name.includes('_0')) {
                el.setAttribute('name', name.replace('_0', '_' + index));
            }
        });
        
        const elementsWithFor = element.querySelectorAll('[for]');
        elementsWithFor.forEach(el => {
            const forAttr = el.getAttribute('for');
            if (forAttr && forAttr.includes('_0')) {
                el.setAttribute('for', forAttr.replace('_0', '_' + index));
            }
        });

        // Atualizar preview id e input de foto para este gerador
        const previewEl = element.querySelector('[id*="geradorPreview"]');
        if (previewEl && previewEl.id.includes('0')) {
            previewEl.id = previewEl.id.replace('0', index);
        }

        const situacaoSelect = element.querySelector('select[name^="gerador_situacao_"]');
        if (situacaoSelect) {
            if (situacaoSelect.id && situacaoSelect.id.includes('_0')) situacaoSelect.id = situacaoSelect.id.replace('_0', `_${index}`);
            if (situacaoSelect.name && situacaoSelect.name.includes('_0')) situacaoSelect.name = situacaoSelect.name.replace('_0', `_${index}`);
            situacaoSelect.setAttribute('onchange', `handleSituacaoChange(this, ${index}, 'gerador')`);
        }
        const valorGroup = element.querySelector('#gerador_valor_recuperacao_group_0');
        if (valorGroup && valorGroup.id.includes('_0')) valorGroup.id = valorGroup.id.replace('_0', `_${index}`);
        const valorInput = element.querySelector('input[name^="gerador_valor_recuperacao_"]');
        if (valorInput) {
            if (valorInput.id && valorInput.id.includes('_0')) valorInput.id = valorInput.id.replace('_0', `_${index}`);
            if (valorInput.name && valorInput.name.includes('_0')) valorInput.name = valorInput.name.replace('_0', `_${index}`);
        }
        const fileInput = element.querySelector('input[id^="gerador_fotos_"]') || element.querySelector('input[name^="gerador_fotos_"]');
        if (fileInput) {
            if (fileInput.id && fileInput.id.includes('_0')) fileInput.id = fileInput.id.replace('_0', `_${index}`);
            if (fileInput.name && fileInput.name.includes('_0')) fileInput.name = fileInput.name.replace('_0', `_${index}`);
            fileInput.setAttribute('onchange', `previewImage(this, 'geradorPreview${index}')`);
        }
    } catch (error) {
        console.error('Erro ao atualizar nomes do gerador:', error);
    }
}

// ==================== FUNÇÕES DE PESSOAL (CORRIGIDAS) ====================

function addPessoal() {
    try {
        console.log('Adicionando pessoal ' + pessoalCount);
        
        const container = document.getElementById('pessoalContainer');
        if (!container) {
            console.log('ℹ️ Layout usa matriz de pessoal; botão de adicionar cartão está inativo.');
            showAlert('Use a grade de pessoal na tabela abaixo (carreira/temporário).', 'info');
            return;
        }
        
        const template = document.getElementById('pessoalTemplate');
        if (!template) {
            alert('Template de pessoal não encontrado');
            return;
        }
        
        const clone = template.content.cloneNode(true);
        const pessoalDiv = clone.querySelector('.pessoal-card');
        
        if (!pessoalDiv) {
            alert('Elemento .pessoal-card não encontrado no template');
            return;
        }
        
        // Atualizar índice
        pessoalDiv.dataset.pessoalIndex = pessoalCount;
        
        // Atualizar número visível
        const numeroSpan = pessoalDiv.querySelector('.pessoal-numero');
        if (numeroSpan) {
            numeroSpan.textContent = pessoalCount + 1;
        }
        
        // Atualizar names
        updatePessoalNames(pessoalDiv, pessoalCount);
        
        // Atualizar event handler de remoção
        const removeBtn = pessoalDiv.querySelector('[onclick="removePessoal(this)"]');
        if (removeBtn) {
            removeBtn.onclick = function() { removePessoal(this); };
        }
        
        container.appendChild(clone);
        
        // Atualizar contador no formulário
        const countInput = document.getElementById('pessoal_count');
        if (countInput) {
            countInput.value = pessoalCount + 1;
        }
        
        pessoalCount++;
        
        showAlert('Pessoal adicionado com sucesso', 'success');
        
    } catch (error) {
        console.error('Erro ao adicionar pessoal:', error);
        alert('Erro ao adicionar pessoal: ' + error.message);
    }
}

function updatePessoalNames(element, index) {
    try {
        const elementsWithName = element.querySelectorAll('[name]');
        elementsWithName.forEach(el => {
            const name = el.getAttribute('name');
            if (name && name.includes('_0')) {
                el.setAttribute('name', name.replace('_0', '_' + index));
            }
        });
        
        const elementsWithFor = element.querySelectorAll('[for]');
        elementsWithFor.forEach(el => {
            const forAttr = el.getAttribute('for');
            if (forAttr && forAttr.includes('_0')) {
                el.setAttribute('for', forAttr.replace('_0', '_' + index));
            }
        });
    } catch (error) {
        console.error('Erro ao atualizar nomes do pessoal:', error);
    }
}

// ==================== FUNÇÕES DE VIATURA (CORRIGIDAS) ====================

function addViatura() {
    try {
        console.log('Adicionando viatura ' + viaturaCount);
        
        const container = document.getElementById('viaturasContainer');
        if (!container) {
            alert('Container de viaturas não encontrado');
            return;
        }
        
        const template = document.getElementById('viaturaTemplate');
        if (!template) {
            alert('Template de viatura não encontrado');
            return;
        }
        
        const clone = template.content.cloneNode(true);
        const viaturaDiv = clone.querySelector('.viatura-card');
        
        if (!viaturaDiv) {
            alert('Elemento .viatura-card não encontrado no template');
            return;
        }
        
        // Atualizar índice
        viaturaDiv.dataset.viaturaIndex = viaturaCount;
        
        // Atualizar names
        updateViaturaNames(viaturaDiv, viaturaCount);

        // Vincular label do cabeçalho ao campo EB
        bindViaturaLabel(viaturaDiv, viaturaCount);

        // Popular select de marcas com opções conhecidas
        const marcaSelectInit = viaturaDiv.querySelector('select[name^="viatura_marca_"]');
        if (marcaSelectInit) {
            Object.keys(VIATURA_BRANDS).forEach(b => {
                const opt = document.createElement('option');
                opt.value = b;
                opt.textContent = b;
                marcaSelectInit.appendChild(opt);
            });
        }

        // Garantir que tipo esteja com comportamento correto ao criar
        const tipoSelectInit = viaturaDiv.querySelector('select[name^="viatura_tipo_"]');
        if (tipoSelectInit) {
            handleTipoChange(tipoSelectInit, viaturaCount);
        }
        // Garantir visibilidade do campo valor_recuperacao conforme situação inicial
        const situacaoSelectInit = viaturaDiv.querySelector('select[name^="viatura_situacao_"]');
        if (situacaoSelectInit) {
            handleSituacaoChange(situacaoSelectInit, viaturaCount, 'viatura');
        }

        
        // Atualizar event handler de remoção
        const removeBtn = viaturaDiv.querySelector('[onclick="removeViatura(this)"]');
        if (removeBtn) {
            removeBtn.onclick = function() { removeViatura(this); };
        }
        
        container.appendChild(clone);
        
        // Atualizar contador no formulário
        const countInput = document.getElementById('viaturas_count');
        if (countInput) {
            countInput.value = viaturaCount + 1;
        }
        
        viaturaCount++;
        
        showAlert('Viatura adicionada com sucesso', 'success');
        
    } catch (error) {
        console.error('Erro ao adicionar viatura:', error);
        alert('Erro ao adicionar viatura: ' + error.message);
    }
}

function bindViaturaLabel(viaturaDiv, index) {
    const label = viaturaDiv.querySelector('.viatura-label');
    const ebInput = viaturaDiv.querySelector(`input[name="viatura_eb_${index}"]`);
    const tipoSelect = viaturaDiv.querySelector(`select[name="viatura_tipo_${index}"]`);
    if (!label || !ebInput) return;
    const update = () => {
        const v = (ebInput.value || '').trim();
        const tipoVal = (tipoSelect && tipoSelect.value) ? tipoSelect.value : '';
        const prefix = tipoVal ? `${tipoVal}` : 'EB';
        label.textContent = v ? `${prefix} ${v}` : 'EB da viatura';
        label.classList.toggle('text-muted', !v);
    };
    ebInput.addEventListener('input', update);
    if (tipoSelect) tipoSelect.addEventListener('change', update);
    update();
}

function updateViaturaNames(element, index) {
    try {
        const elementsWithName = element.querySelectorAll('[name]');
        elementsWithName.forEach(el => {
            const name = el.getAttribute('name');
            if (name && name.includes('_0')) {
                el.setAttribute('name', name.replace('_0', '_' + index));
            }
        });
        
        const elementsWithFor = element.querySelectorAll('[for]');
        elementsWithFor.forEach(el => {
            const forAttr = el.getAttribute('for');
            if (forAttr && forAttr.includes('_0')) {
                el.setAttribute('for', forAttr.replace('_0', '_' + index));
            }
        });

        // Atualizar preview e input de fotos
        const previewEl = element.querySelector('[id*="viaturaPreview"]');
        if (previewEl && previewEl.id.includes('0')) {
            previewEl.id = previewEl.id.replace('0', index);
        }

        const fileInput = element.querySelector('input[id^="viatura_fotos_"]') || element.querySelector('input[name^="viatura_fotos_"]');
        if (fileInput) {
            if (fileInput.id && fileInput.id.includes('_0')) fileInput.id = fileInput.id.replace('_0', `_${index}`);
            if (fileInput.name && fileInput.name.includes('_0')) fileInput.name = fileInput.name.replace('_0', `_${index}`);
            fileInput.setAttribute('onchange', `previewImage(this, 'viaturaPreview${index}')`);
        }

        // Atualizar selects de marca/modelo e tipo/especializacao
        const marcaSelect = element.querySelector('select[name^="viatura_marca_"]');
        if (marcaSelect) {
            if (marcaSelect.id && marcaSelect.id.includes('_0')) marcaSelect.id = marcaSelect.id.replace('_0', `_${index}`);
            if (marcaSelect.name && marcaSelect.name.includes('_0')) marcaSelect.name = marcaSelect.name.replace('_0', `_${index}`);
            marcaSelect.setAttribute('onchange', `populateModelos(this, ${index})`);
        }
        const modeloSelect = element.querySelector('select[name^="viatura_modelo_"]');
        if (modeloSelect) {
            if (modeloSelect.id && modeloSelect.id.includes('_0')) modeloSelect.id = modeloSelect.id.replace('_0', `_${index}`);
            if (modeloSelect.name && modeloSelect.name.includes('_0')) modeloSelect.name = modeloSelect.name.replace('_0', `_${index}`);
        }
        const tipoSelect = element.querySelector('select[name^="viatura_tipo_"]');
        if (tipoSelect) {
            if (tipoSelect.id && tipoSelect.id.includes('_0')) tipoSelect.id = tipoSelect.id.replace('_0', `_${index}`);
            if (tipoSelect.name && tipoSelect.name.includes('_0')) tipoSelect.name = tipoSelect.name.replace('_0', `_${index}`);
            tipoSelect.setAttribute('onchange', `handleTipoChange(this, ${index})`);
        }
        const situacaoSelect = element.querySelector('select[name^="viatura_situacao_"]');
        if (situacaoSelect) {
            if (situacaoSelect.id && situacaoSelect.id.includes('_0')) situacaoSelect.id = situacaoSelect.id.replace('_0', `_${index}`);
            if (situacaoSelect.name && situacaoSelect.name.includes('_0')) situacaoSelect.name = situacaoSelect.name.replace('_0', `_${index}`);
            situacaoSelect.setAttribute('onchange', `handleSituacaoChange(this, ${index}, 'viatura')`);
        }
        const especialGroup = element.querySelector('#viatura_especializacao_group_0');
        if (especialGroup && especialGroup.id.includes('_0')) especialGroup.id = especialGroup.id.replace('_0', `_${index}`);
        const especialSelect = element.querySelector('select[name^="viatura_especializacao_"]');
        if (especialSelect) {
            if (especialSelect.id && especialSelect.id.includes('_0')) especialSelect.id = especialSelect.id.replace('_0', `_${index}`);
            if (especialSelect.name && especialSelect.name.includes('_0')) especialSelect.name = especialSelect.name.replace('_0', `_${index}`);
        }
    } catch (error) {
        console.error('Erro ao atualizar nomes da viatura:', error);
    }
}

// ==================== FUNÇÕES AUXILIARES (MANTIDAS) ====================

function removeGerador(button) {
    try {
        const geradorCard = button.closest('.gerador-card');
        if (!geradorCard) return;
        
        geradorCard.remove();
        showAlert('Gerador removido', 'info');
        
        renumberGeradores();
    } catch (error) {
        console.error('Erro ao remover gerador:', error);
    }
}

function renumberGeradores() {
    try {
        const geradores = document.querySelectorAll('.gerador-card');
        geradorCount = 0;
        
        geradores.forEach((gerador, index) => {
            gerador.dataset.geradorIndex = geradorCount;
            const numeroSpan = gerador.querySelector('.gerador-numero');
            if (numeroSpan) {
                numeroSpan.textContent = geradorCount + 1;
            }
            updateGeradorNames(gerador, geradorCount);
            collapseCard(gerador);
            geradorCount++;
        });
        
        const countInput = document.getElementById('geradores_count');
        if (countInput) {
            countInput.value = geradorCount;
        }
    } catch (error) {
        console.error('Erro ao renumerar geradores:', error);
    }
}

function removePessoal(button) {
    try {
        const pessoalCard = button.closest('.pessoal-card');
        if (!pessoalCard) return;
        
        pessoalCard.remove();
        showAlert('Pessoal removido', 'info');
        
        renumberPessoal();
    } catch (error) {
        console.error('Erro ao remover pessoal:', error);
    }
}

function renumberPessoal() {
    try {
        const pessoalItems = document.querySelectorAll('.pessoal-card');
        pessoalCount = 0;
        
        pessoalItems.forEach((pessoal, index) => {
            pessoal.dataset.pessoalIndex = pessoalCount;
            const numeroSpan = pessoal.querySelector('.pessoal-numero');
            if (numeroSpan) {
                numeroSpan.textContent = pessoalCount + 1;
            }
            updatePessoalNames(pessoal, pessoalCount);
            pessoalCount++;
        });
        
        const countInput = document.getElementById('pessoal_count');
        if (countInput) {
            countInput.value = pessoalCount;
        }
    } catch (error) {
        console.error('Erro ao renumerar pessoal:', error);
    }
}

function removeViatura(button) {
    try {
        const viaturaCard = button.closest('.viatura-card');
        if (!viaturaCard) return;
        
        viaturaCard.remove();
        showAlert('Viatura removida', 'info');
        
        renumberViaturas();
    } catch (error) {
        console.error('Erro ao remover viatura:', error);
    }
}

function renumberViaturas() {
    try {
        const viaturas = document.querySelectorAll('.viatura-card');
        viaturaCount = 0;
        
        viaturas.forEach((viatura, index) => {
            viatura.dataset.viaturaIndex = viaturaCount;
            updateViaturaNames(viatura, viaturaCount);
            bindViaturaLabel(viatura, viaturaCount);
            viaturaCount++;
        });
        
        const countInput = document.getElementById('viaturas_count');
        if (countInput) {
            countInput.value = viaturaCount;
        }
    } catch (error) {
        console.error('Erro ao renumerar viaturas:', error);
    }
}

// Lista de marcas e modelos (uso interno para popular selects)
// Ampliada para contemplar principalmente caminhões usados pelas Forças Armadas e frotas logísticas
const VIATURA_BRANDS = {
    'Agrale': ['Marruá AM20', 'Marruá AM21'],
    'Toyota': ['Hilux', 'SW4', 'Land Cruiser'],
    'Ford': ['Ranger', 'F-4000', 'Cargo'],
    'Chevrolet': ['S10', 'NHR (light truck)'],
    'Volkswagen': ['Amarok', 'Delivery', 'Constellation', 'Worker'],
    'Mercedes-Benz': ['Unimog', 'Sprinter', 'Accelo', 'Atego', 'Axor', 'Actros'],
    'Iveco': ['Daily', 'Tector', 'Stralis'],
    'Nissan': ['Frontier', 'NT500'],
    'Volvo': ['FH', 'FM', 'VM'],
    'Scania': ['R-Series', 'P-Series', 'G-Series'],
    'MAN': ['TGX', 'TGS'],
    'DAF': ['XF', 'LF'],
    'Renault': ['Master', 'Midlum', 'Premium'],
    'Hino': ['300', '500'],
    'Isuzu': ['NQR', 'NPR']
};

function populateModelos(select, index) {
    try {
        const marca = select.value;
        const modeloSelect = document.getElementById(`viatura_modelo_${index}`);
        if (!modeloSelect) return;
        modeloSelect.innerHTML = '<option value="">Selecione modelo</option>';
        if (!marca) return;
        const modelos = VIATURA_BRANDS[marca] || [];
        modelos.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m;
            opt.textContent = m;
            modeloSelect.appendChild(opt);
        });
    } catch (error) {
        console.error('Erro ao popular modelos:', error);
    }
}

function handleTipoChange(select, index) {
    try {
        const group = document.getElementById(`viatura_especializacao_group_${index}`);
        if (!group) return;
        if (select.value === 'VTE') {
            group.classList.remove('d-none');
        } else {
            group.classList.add('d-none');
            const sel = group.querySelector('select');
            if (sel) sel.value = '';
        }
    } catch (error) {
        console.error('Erro em handleTipoChange:', error);
    }
}

function removeInstalacao(button) {
    try {
        const instalacaoCard = button.closest('.instalacao-card');
        if (!instalacaoCard) return;
        
        // Obter índice antes de remover
        const index = parseInt(instalacaoCard.dataset.index);
        
        instalacaoCard.remove();
        showAlert('Instalação removida', 'info');
        
        // Reorganizar números das instalações
        renumberInstalacoes();
        
        // Remover contadores deste índice
        delete empilhadeiraCounts[index];
        delete sistemaCounts[index];
        delete equipamentoCounts[index];
    } catch (error) {
        console.error('Erro ao remover instalação:', error);
    }
}

function renumberInstalacoes() {
    try {
        const instalacoes = document.querySelectorAll('.instalacao-card');
        instalacaoCount = 0;
        
        instalacoes.forEach((instalacao, index) => {
            const oldIndex = parseInt(instalacao.dataset.index) || index;
            instalacao.dataset.index = instalacaoCount;
            
            // Atualizar número visível
            const numeroSpan = instalacao.querySelector('.instalacao-numero');
            if (numeroSpan) {
                numeroSpan.textContent = instalacaoCount + 1;
            }
            
            // Atualizar names e IDs
            updateInstalacaoIdsAndNames(instalacao, instalacaoCount);
            
            // Reconfigurar event listeners
            const tipoSelect = instalacao.querySelector('select[name^="tipo_instalacao_"]');
            if (tipoSelect) {
                // Clonar para remover event listeners antigos
                const newSelect = tipoSelect.cloneNode(true);
                tipoSelect.parentNode.replaceChild(newSelect, tipoSelect);
                
                // Adicionar novo event listener
                newSelect.addEventListener('change', function() {
                    toggleDepositoSubsecoes(this, instalacaoCount);
                });
            }
            
            // Mover contadores para o novo índice
            if (empilhadeiraCounts[oldIndex] !== undefined) {
                empilhadeiraCounts[instalacaoCount] = empilhadeiraCounts[oldIndex];
                delete empilhadeiraCounts[oldIndex];
                const empCountInput = document.getElementById(`empilhadeiras_count_${instalacaoCount}`);
                if (empCountInput) empCountInput.value = empilhadeiraCounts[instalacaoCount];
            }
            
            if (sistemaCounts[oldIndex] !== undefined) {
                sistemaCounts[instalacaoCount] = sistemaCounts[oldIndex];
                delete sistemaCounts[oldIndex];
                const sisCountInput = document.getElementById(`sistemas_count_${instalacaoCount}`);
                if (sisCountInput) sisCountInput.value = sistemaCounts[instalacaoCount];
            }
            
            if (equipamentoCounts[oldIndex] !== undefined) {
                equipamentoCounts[instalacaoCount] = equipamentoCounts[oldIndex];
                delete equipamentoCounts[oldIndex];
                const eqCountInput = document.getElementById(`equipamentos_count_${instalacaoCount}`);
                if (eqCountInput) eqCountInput.value = equipamentoCounts[instalacaoCount];
            }
            
            instalacaoCount++;
        });
        
        const countInput = document.getElementById('instalacoes_count');
        if (countInput) {
            countInput.value = instalacaoCount;
        }
    } catch (error) {
        console.error('Erro ao renumerar instalações:', error);
    }
}

// ==================== FUNÇÕES DE SUBSISTEMAS (MANTIDAS) ====================

function addEmpilhadeira(instalacaoIndex) {
    try {
        console.log('Adicionando empilhadeira na instalação ' + instalacaoIndex);
        
        const container = document.getElementById(`empilhadeirasContainer${instalacaoIndex}`);
        if (!container) {
            console.error(`Container empilhadeirasContainer${instalacaoIndex} não encontrado`);
            alert('Container de empilhadeiras não encontrado');
            return;
        }
        
        const template = document.getElementById('empilhadeiraTemplate');
        if (!template) {
            alert('Template de empilhadeira não encontrado');
            return;
        }
        
        const clone = template.content.cloneNode(true);
        const subItem = clone.querySelector('.sub-item');
        
        if (!subItem) {
            alert('Elemento .sub-item não encontrado no template');
            return;
        }
        
        // Obter próximo índice para esta instalação
        const subIndex = empilhadeiraCounts[instalacaoIndex] || 0;
        
        // Atualizar names
        updateSubItemNames(subItem, instalacaoIndex, subIndex, 'empilhadeira');

        // Ajustar título numérico
        updateEmpilhadeiraTitulos(instalacaoIndex, container);
        
        // Configurar botão de remover
        const removeBtn = subItem.querySelector('button[onclick*="removeSubItem"]');
        if (removeBtn) {
            removeBtn.onclick = function() { 
                removeSubItem(this, 'empilhadeira', instalacaoIndex, subIndex); 
            };
        }
        
        container.appendChild(clone);

        // Reaplicar atualização após inserir no DOM (garante atributos em elementos aninhados)
        const appended = container.querySelectorAll('.sub-item');
        const lastSubItem = appended[appended.length - 1];
        if (lastSubItem) {
            updateSubItemNames(lastSubItem, instalacaoIndex, subIndex, 'empilhadeira');
            // Debug: log names para verificar envio ao backend
            const dbgNames = Array.from(lastSubItem.querySelectorAll('[name]')).map(el => el.name);
            console.log('[DEBUG empilhadeira names]', dbgNames);
            updateEmpilhadeiraTitulos(instalacaoIndex, container);
        }
        
        // Incrementar contador
        empilhadeiraCounts[instalacaoIndex] = (empilhadeiraCounts[instalacaoIndex] || 0) + 1;
        
        // Atualizar contador no formulário
        const empCountInput = document.getElementById(`empilhadeiras_count_${instalacaoIndex}`);
        if (empCountInput) {
            empCountInput.value = empilhadeiraCounts[instalacaoIndex];
        }
        
        showAlert('Empilhadeira adicionada', 'success');
        
    } catch (error) {
        console.error('Erro ao adicionar empilhadeira:', error);
        alert('Erro ao adicionar empilhadeira: ' + error.message);
    }
}

function addSistemaSeguranca(instalacaoIndex) {
    try {
        console.log('Adicionando sistema de segurança na instalação ' + instalacaoIndex);
        
        const container = document.getElementById(`sistemasContainer${instalacaoIndex}`);
        if (!container) {
            console.error(`Container sistemasContainer${instalacaoIndex} não encontrado`);
            alert('Container de sistemas não encontrado');
            return;
        }
        
        const template = document.getElementById('sistemaTemplate');
        if (!template) {
            alert('Template de sistema não encontrado');
            return;
        }
        
        const clone = template.content.cloneNode(true);
        const subItem = clone.querySelector('.sub-item');
        
        if (!subItem) {
            alert('Elemento .sub-item não encontrado no template');
            return;
        }
        
        // Obter próximo índice para esta instalação
        const subIndex = sistemaCounts[instalacaoIndex] || 0;
        
        // Atualizar names
        updateSubItemNames(subItem, instalacaoIndex, subIndex, 'sistema');
        
        // Configurar botão de remover
        const removeBtn = subItem.querySelector('button[onclick*="removeSubItem"]');
        if (removeBtn) {
            removeBtn.onclick = function() { 
                removeSubItem(this, 'sistema', instalacaoIndex, subIndex); 
            };
        }
        
        container.appendChild(clone);

        // Reaplicar atualização após inserir no DOM (garante atributos em elementos aninhados)
        const appended = container.querySelectorAll('.sub-item');
        const lastSubItem = appended[appended.length - 1];
        if (lastSubItem) {
            updateSubItemNames(lastSubItem, instalacaoIndex, subIndex, 'sistema');
            const dbgNames = Array.from(lastSubItem.querySelectorAll('[name]')).map(el => el.name);
            console.log('[DEBUG sistema names]', dbgNames);
        }
        
        // Incrementar contador
        sistemaCounts[instalacaoIndex] = (sistemaCounts[instalacaoIndex] || 0) + 1;
        
        // Atualizar contador no formulário
        const sisCountInput = document.getElementById(`sistemas_count_${instalacaoIndex}`);
        if (sisCountInput) {
            sisCountInput.value = sistemaCounts[instalacaoIndex];
        }
        
        showAlert('Sistema de segurança adicionado', 'success');
        
    } catch (error) {
        console.error('Erro ao adicionar sistema:', error);
        alert('Erro ao adicionar sistema: ' + error.message);
    }
}

function addEquipamentoUnitizacao(instalacaoIndex) {
    try {
        console.log('Adicionando equipamento de unitização na instalação ' + instalacaoIndex);
        
        const container = document.getElementById(`equipamentosContainer${instalacaoIndex}`);
        if (!container) {
            console.error(`Container equipamentosContainer${instalacaoIndex} não encontrado`);
            alert('Container de equipamentos não encontrado');
            return;
        }
        
        const template = document.getElementById('equipamentoTemplate');
        if (!template) {
            alert('Template de equipamento não encontrado');
            return;
        }
        
        const clone = template.content.cloneNode(true);
        const subItem = clone.querySelector('.sub-item');
        
        if (!subItem) {
            alert('Elemento .sub-item não encontrado no template');
            return;
        }
        
        // Obter próximo índice para esta instalação
        const subIndex = equipamentoCounts[instalacaoIndex] || 0;
        
        // Atualizar names
        updateSubItemNames(subItem, instalacaoIndex, subIndex, 'equipamento');

        // Atualizar título com o tipo selecionado e ouvir mudanças
        const tipoSelect = subItem.querySelector('[data-field="eq-tipo"]');
        if (tipoSelect) {
            tipoSelect.addEventListener('change', () => {
                updateEquipamentoTitulo(subItem, tipoSelect);
            });
            updateEquipamentoTitulo(subItem, tipoSelect);
        }
        
        // Configurar botão de remover
        const removeBtn = subItem.querySelector('button[onclick*="removeSubItem"]');
        if (removeBtn) {
            removeBtn.onclick = function() { 
                removeSubItem(this, 'equipamento', instalacaoIndex, subIndex); 
            };
        }
        
        container.appendChild(clone);

        // Reaplicar atualização após inserir no DOM (garante atributos em elementos aninhados)
        const appended = container.querySelectorAll('.sub-item');
        const lastSubItem = appended[appended.length - 1];
        if (lastSubItem) {
            updateSubItemNames(lastSubItem, instalacaoIndex, subIndex, 'equipamento');
            const dbgNames = Array.from(lastSubItem.querySelectorAll('[name]')).map(el => el.name);
            console.log('[DEBUG equipamento names]', dbgNames);
            const tipoSel = lastSubItem.querySelector('[data-field="eq-tipo"]');
            if (tipoSel) updateEquipamentoTitulo(lastSubItem, tipoSel);
        }
        
        // Incrementar contador
        equipamentoCounts[instalacaoIndex] = (equipamentoCounts[instalacaoIndex] || 0) + 1;
        
        // Atualizar contador no formulário
        const eqCountInput = document.getElementById(`equipamentos_count_${instalacaoIndex}`);
        if (eqCountInput) {
            eqCountInput.value = equipamentoCounts[instalacaoIndex];
        }
        
        showAlert('Equipamento de unitização adicionado', 'success');
        
    } catch (error) {
        console.error('Erro ao adicionar equipamento:', error);
        alert('Erro ao adicionar equipamento: ' + error.message);
    }
}

// ==================== FUNÇÕES DE SUBSISTEMAS - CONTINUAÇÃO ====================

function removeSubItem(button, type, instalacaoIndex, subIndex) {
    try {
        const subItem = button.closest('.sub-item');
        if (!subItem) return;
        
        subItem.remove();
        
        // Decrementar contador
        switch(type) {
            case 'empilhadeira':
                if (empilhadeiraCounts[instalacaoIndex] > 0) {
                    empilhadeiraCounts[instalacaoIndex]--;
                    const empCountInput = document.getElementById(`empilhadeiras_count_${instalacaoIndex}`);
                    if (empCountInput) empCountInput.value = empilhadeiraCounts[instalacaoIndex];
                }
                updateEmpilhadeiraTitulos(instalacaoIndex);
                break;
            case 'sistema':
                if (sistemaCounts[instalacaoIndex] > 0) {
                    sistemaCounts[instalacaoIndex]--;
                    const sisCountInput = document.getElementById(`sistemas_count_${instalacaoIndex}`);
                    if (sisCountInput) sisCountInput.value = sistemaCounts[instalacaoIndex];
                }
                break;
            case 'equipamento':
                if (equipamentoCounts[instalacaoIndex] > 0) {
                    equipamentoCounts[instalacaoIndex]--;
                    const eqCountInput = document.getElementById(`equipamentos_count_${instalacaoIndex}`);
                    if (eqCountInput) eqCountInput.value = equipamentoCounts[instalacaoIndex];
                }
                break;
        }
        
        showAlert('Item removido', 'info');
    } catch (error) {
        console.error('Erro ao remover sub-item:', error);
    }
}

function updateSubItemNames(subItem, instalacaoIndex, subIndex, prefix) {
    try {
        const replaceIdx = (text) => text
            .replace(/{{\s*index\s*}}/g, `${instalacaoIndex}`)
            .replace(/{{\s*subIndex\s*}}/g, `${subIndex}`)
            .replace(/_0_0/g, `_${instalacaoIndex}_${subIndex}`);

        // Atualizar atributos name/id/for em todos os elementos do sub-item
        subItem.querySelectorAll('[name], [id], label[for]').forEach(el => {
            if (el.name) {
                el.name = replaceIdx(el.name);
            }
            if (el.id) {
                el.id = replaceIdx(el.id);
            }
            if (el.tagName === 'LABEL' && el.htmlFor) {
                el.htmlFor = replaceIdx(el.htmlFor);
            }
        });

        // Ajuste específico de valorRecuperacao id
        const valorRec = subItem.querySelector('[id^="valorRecuperacaoEmpilhadeira_"]');
        if (valorRec) {
            valorRec.id = `valorRecuperacaoEmpilhadeira_${instalacaoIndex}_${subIndex}`;
        }

        // Ajuste explícito para empilhadeira: forçar nomes/ids conhecidos (sem querySelector com chaves)
        if (prefix === 'empilhadeira') {
            const map = [
                { field: 'tipo', selector: '[data-field="emp-tipo"]' },
                { field: 'capacidade', selector: '[data-field="emp-capacidade"]' },
                { field: 'quantidade', selector: '[data-field="emp-quantidade"]' },
                { field: 'ano', selector: '[data-field="emp-ano"]' },
                { field: 'situacao', selector: '[data-field="emp-situacao"]' },
                { field: 'valor_recuperacao', selector: '[data-field="emp-valor-recuperacao"]' },
                { field: 'fotos', selector: '[data-field="emp-fotos"]' }
            ];

            map.forEach(({ field, selector }) => {
                const input = subItem.querySelector(selector) || subItem.querySelector(`[name^="empilhadeira_${field}_"]`);
                if (input) {
                    const baseName = `empilhadeira_${field}_${instalacaoIndex}_${subIndex}`;
                    input.name = field === 'fotos' ? `${baseName}[]` : baseName;
                    input.id = baseName;
                }
            });

            // Normalizar qualquer name/id que tenha ficado com '__'
            subItem.querySelectorAll('[name], [id]').forEach(el => {
                if (el.name && /empilhadeira_/.test(el.name) && el.name.endsWith('__')) {
                    const parts = el.name.split('_');
                    const field = parts[1] || 'campo';
                    el.name = field === 'fotos'
                        ? `empilhadeira_${field}_${instalacaoIndex}_${subIndex}[]`
                        : `empilhadeira_${field}_${instalacaoIndex}_${subIndex}`;
                }
                if (el.id && /empilhadeira_/.test(el.id) && el.id.endsWith('__')) {
                    const parts = el.id.split('_');
                    const field = parts[1] || 'campo';
                    el.id = `empilhadeira_${field}_${instalacaoIndex}_${subIndex}`;
                }
            });
        }

        // Ajuste explícito para sistema de segurança
        if (prefix === 'sistema') {
            const map = [
                { field: 'tipo', selector: '[data-field="sis-tipo"]' },
                { field: 'quantidade', selector: '[data-field="sis-quantidade"]' },
                { field: 'situacao', selector: '[data-field="sis-situacao"]' },
                { field: 'descricao', selector: '[data-field="sis-descricao"]' }
            ];

            map.forEach(({ field, selector }) => {
                const input = subItem.querySelector(selector) || subItem.querySelector(`[name^="sistema_${field}_"]`);
                if (input) {
                    const baseName = `sistema_${field}_${instalacaoIndex}_${subIndex}`;
                    input.name = baseName;
                    input.id = baseName;
                }
            });

            subItem.querySelectorAll('[name], [id]').forEach(el => {
                if (el.name && /sistema_/.test(el.name) && el.name.endsWith('__')) {
                    const parts = el.name.split('_');
                    const field = parts[1] || 'campo';
                    el.name = `sistema_${field}_${instalacaoIndex}_${subIndex}`;
                }
                if (el.id && /sistema_/.test(el.id) && el.id.endsWith('__')) {
                    const parts = el.id.split('_');
                    const field = parts[1] || 'campo';
                    el.id = `sistema_${field}_${instalacaoIndex}_${subIndex}`;
                }
            });
        }

        // Ajuste explícito para equipamento de unitização
        if (prefix === 'equipamento') {
            const map = [
                { field: 'tipo', selector: '[data-field="eq-tipo"]' },
                { field: 'capacidade', selector: '[data-field="eq-capacidade"]' },
                { field: 'quantidade', selector: '[data-field="eq-quantidade"]' },
                { field: 'observacoes', selector: '[data-field="eq-observacoes"]' }
            ];

            map.forEach(({ field, selector }) => {
                const input = subItem.querySelector(selector) || subItem.querySelector(`[name^="equipamento_${field}_"]`);
                if (input) {
                    const baseName = `equipamento_${field}_${instalacaoIndex}_${subIndex}`;
                    input.name = baseName;
                    input.id = baseName;
                }
            });

            subItem.querySelectorAll('[name], [id]').forEach(el => {
                if (el.name && /equipamento_/.test(el.name) && el.name.endsWith('__')) {
                    const parts = el.name.split('_');
                    const field = parts[1] || 'campo';
                    el.name = `equipamento_${field}_${instalacaoIndex}_${subIndex}`;
                }
                if (el.id && /equipamento_/.test(el.id) && el.id.endsWith('__')) {
                    const parts = el.id.split('_');
                    const field = parts[1] || 'campo';
                    el.id = `equipamento_${field}_${instalacaoIndex}_${subIndex}`;
                }
            });
        }
    } catch (error) {
        console.error('Erro ao atualizar nomes do sub-item:', error);
    }
}

// Renumera os títulos das empilhadeiras para "Empilhadeira 1, 2, ..."
function updateEmpilhadeiraTitulos(instalacaoIndex, containerRef) {
    try {
        const container = containerRef || document.getElementById(`empilhadeirasContainer${instalacaoIndex}`);
        if (!container) return;
        const titles = container.querySelectorAll('.empilhadeira-title');
        titles.forEach((title, idx) => {
            title.textContent = `Empilhadeira ${idx + 1}`;
        });
    } catch (err) {
        console.error('Erro ao renumerar empilhadeiras:', err);
    }
}

// Atualiza o título do equipamento para exibir o tipo escolhido
function updateEquipamentoTitulo(subItem, selectEl) {
    try {
        const titleEl = subItem ? subItem.querySelector('.equipamento-title') : null;
        if (!titleEl) return;
        const text = selectEl && selectEl.selectedOptions && selectEl.selectedOptions[0]
            ? selectEl.selectedOptions[0].textContent.trim()
            : '';
        titleEl.textContent = text ? `Equipamento: ${text}` : 'Equipamento de Unitização';
    } catch (err) {
        console.error('Erro ao atualizar título do equipamento:', err);
    }
}

function toggleDepositoSubsecoes(selectElement, instalacaoIndex) {
    try {
        const valor = selectElement.value;
        
        // Lista de tipos de instalação que são depósitos
        const tiposDeposito = [
            'deposito_cl1_seco', 'deposito_cl1_frigo', 'deposito_cl2', 'deposito_cl3', 'deposito_cl4',
            'deposito_cl5', 'deposito_cl6', 'deposito_cl7', 'deposito_cl8', 'deposito_cl9', 'deposito_cl10'
        ];
        
        const isDeposito = tiposDeposito.includes(valor);
        
        // Encontrar os elementos pelo ID
        const verticalizacaoGroupId = `verticalizacaoGroup_${instalacaoIndex}`;
        const depositoSubsecoesId = `depositoSubsecoes_${instalacaoIndex}`;
        const capacidadeId = `capacidade_${instalacaoIndex}`;
        
        const verticalizacaoGroup = document.getElementById(verticalizacaoGroupId);
        const depositoSubsecoes = document.getElementById(depositoSubsecoesId);
        const capacidadeInput = document.getElementById(capacidadeId);

        // Habilitar / desabilitar capacidade em toneladas
        if (capacidadeInput) {
            capacidadeInput.disabled = !isDeposito;
            capacidadeInput.placeholder = isDeposito ? 'Ex: 100.00' : 'Habilitado apenas para depósitos';
            if (!isDeposito) capacidadeInput.value = '';
        }
        
        // Mostrar/ocultar verticalização
        if (verticalizacaoGroup) {
            if (isDeposito) {
                verticalizacaoGroup.style.display = 'block';
            } else {
                verticalizacaoGroup.style.display = 'none';
                // Limpar valor se campo estiver escondido
                const verticalizacaoSelect = verticalizacaoGroup.querySelector('select');
                if (verticalizacaoSelect) {
                    verticalizacaoSelect.value = '';
                }
            }
        }
        
        // Mostrar/ocultar subseções de depósito
        if (depositoSubsecoes) {
            if (isDeposito) {
                depositoSubsecoes.style.display = 'block';
            } else {
                depositoSubsecoes.style.display = 'none';
                // Limpar todos os sub-itens se não for depósito
                clearDepositoSubitems(instalacaoIndex);
            }
        }

        // Habilitar ou desabilitar botões de sub-itens
        try {
            const card = document.querySelector(`.instalacao-card[data-index="${instalacaoIndex}"]`);
            if (card) {
                card.querySelectorAll('[data-role="subitem-btn"]').forEach(btn => {
                    btn.disabled = !isDeposito;
                    btn.title = isDeposito ? '' : 'Disponível apenas para depósitos';
                });
            }
        } catch (err) {
            console.error('Erro ao alternar botões de sub-itens:', err);
        }
    } catch (error) {
        console.error('Erro ao alternar subseções de depósito:', error);
    }
}

function clearDepositoSubitems(instalacaoIndex) {
    try {
        // Limpar empilhadeiras
        const empContainer = document.getElementById(`empilhadeirasContainer${instalacaoIndex}`);
        if (empContainer) {
            empContainer.innerHTML = '';
            empilhadeiraCounts[instalacaoIndex] = 0;
            const empCountInput = document.getElementById(`empilhadeiras_count_${instalacaoIndex}`);
            if (empCountInput) empCountInput.value = 0;
        }
        
        // Limpar sistemas
        const sisContainer = document.getElementById(`sistemasContainer${instalacaoIndex}`);
        if (sisContainer) {
            sisContainer.innerHTML = '';
            sistemaCounts[instalacaoIndex] = 0;
            const sisCountInput = document.getElementById(`sistemas_count_${instalacaoIndex}`);
            if (sisCountInput) sisCountInput.value = 0;
        }
        
        // Limpar equipamentos
        const eqContainer = document.getElementById(`equipamentosContainer${instalacaoIndex}`);
        if (eqContainer) {
            eqContainer.innerHTML = '';
            equipamentoCounts[instalacaoIndex] = 0;
            const eqCountInput = document.getElementById(`equipamentos_count_${instalacaoIndex}`);
            if (eqCountInput) eqCountInput.value = 0;
        }
    } catch (error) {
        console.error('Erro ao limpar sub-itens:', error);
    }
}

function setupExistingInstalacoes() {
    try {
        console.log('Configurando instalações existentes...');
        
        const instalacoes = document.querySelectorAll('.instalacao-card');
        instalacoes.forEach((instalacao) => {
            const instalacaoIndex = parseInt(instalacao.dataset.index) || 0;
            
            // Configurar select de tipo de instalação
            const tipoSelect = instalacao.querySelector(`select[name^="tipo_instalacao_"]`);
            if (tipoSelect) {
                tipoSelect.addEventListener('change', function() {
                    toggleDepositoSubsecoes(this, instalacaoIndex);
                });
                
                // Verificar se já tem um valor selecionado
                if (tipoSelect.value) {
                    setTimeout(() => {
                        toggleDepositoSubsecoes(tipoSelect, instalacaoIndex);
                    }, 50);
                }
            }
        });
    } catch (error) {
        console.error('Erro ao configurar instalações existentes:', error);
    }
}

// ==================== FUNÇÕES DE ALERTA ====================

function showAlert(message, type) {
    try {
        // Criar alerta simples
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-' + type;
        alertDiv.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 10000;
            max-width: 300px;
            padding: 15px;
            border-radius: 4px;
            animation: slideIn 0.3s ease;
        `;
        
        // Adicionar ícone baseado no tipo
        let icon = 'info-circle';
        if (type === 'success') icon = 'check-circle';
        if (type === 'error') icon = 'exclamation-circle';
        
        alertDiv.innerHTML = `
            <i class="fas fa-${icon}" style="margin-right: 10px;"></i>
            ${message}
        `;
        
        document.body.appendChild(alertDiv);
        
        // Remover após 3 segundos
        setTimeout(() => {
            alertDiv.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => {
                if (alertDiv.parentElement) {
                    alertDiv.remove();
                }
            }, 300);
        }, 3000);
    } catch (error) {
        console.error('Erro ao mostrar alerta:', error);
    }
}

// ==================== VALIDAÇÃO DO FORMULÁRIO ====================

function validarFormulario() {
    try {
        // Validar OMs selecionadas
        const omsSelecionadasInput = document.getElementById('oms_selecionadas');
        const omsSelecionadas = omsSelecionadasInput.value.split(',').filter(om => om.trim() !== '');
        
        if (omsSelecionadas.length === 0) {
            showAlert('Por favor, selecione pelo menos uma OM que apoia.', 'error');
            // Voltar para a aba de dados gerais
            if (typeof mudarAba === 'function') {
                mudarAba(0);
            }
            return false;
        }
        
        // Não bloquear envio por capacidade ou geradores; servidor lidará com dados ausentes
        return true;
    } catch (error) {
        console.error('Erro na validação do formulário:', error);
        return false;
    }
}

// ==================== CONFIGURAÇÃO DE ENVIO DO FORMULÁRIO ====================

function configurarEnvioFormulario() {
    try {
        const form = document.getElementById('cadastroForm');
        if (form) {
            form.addEventListener('submit', function(event) {
                if (typeof validarFormulario === 'function' && !validarFormulario()) {
                    event.preventDefault();
                    return false;
                }

                // Serializar matriz de pessoal em inputs ocultos para envio normal
                if (typeof serializePessoalMatrix === 'function') {
                    const ok = serializePessoalMatrix(form);
                    if (!ok) {
                        event.preventDefault();
                        return false;
                    }
                }

                // Log auxiliar: verificar marcador e count de pessoal
                try {
                    const payload = form.querySelector('input[name="pessoal_payload"]')?.value;
                    const pcount = form.querySelector('#pessoal_count')?.value;
                    console.log('[SUBMIT] pessoal_payload=', payload, 'pessoal_count=', pcount);
                } catch (err) {
                    console.warn('Não foi possível logar payload de pessoal', err);
                }

                // Sincronizar contadores hidden com o DOM para garantir que o back-end processe todos os itens
                try {
                    const setVal = (id, val) => {
                        const el = document.getElementById(id);
                        if (el) el.value = val;
                    };
                    setVal('instalacoes_count', document.querySelectorAll('.instalacao-card').length);
                    setVal('geradores_count', document.querySelectorAll('.gerador-card').length);
                    setVal('viaturas_count', document.querySelectorAll('.viatura-card').length);
                    // Não sobrescrever pessoal_count se já foi gerado pela matriz
                    const pc = document.getElementById('pessoal_count');
                    if (pc && pc.dataset.generated === 'pessoal') {
                        // manter valor definido pelo serializePessoalMatrix
                    } else {
                        setVal('pessoal_count', document.querySelectorAll('.pessoal-card').length);
                    }
                } catch (err) {
                    console.error('Erro ao sincronizar contadores antes do submit:', err);
                }

                // Validation passed — allow submit to continue
                return true;
            });
        }
    } catch (error) {
        console.error('Erro ao configurar envio do formulário:', error);
    }
}

// ==================== EXPOR FUNÇÕES GLOBALMENTE ====================

window.addInstalacao = addInstalacao;
window.removeInstalacao = removeInstalacao;
window.addViatura = addViatura;
window.removeViatura = removeViatura;
window.addPessoal = addPessoal;
window.removePessoal = removePessoal;
window.addGerador = addGerador;
window.removeGerador = removeGerador;
window.addEmpilhadeira = addEmpilhadeira;
window.addSistemaSeguranca = addSistemaSeguranca;
window.addEquipamentoUnitizacao = addEquipamentoUnitizacao;
window.removeSubItem = removeSubItem;
window.toggleDepositoSubsecoes = toggleDepositoSubsecoes;
window.clearDepositoSubitems = clearDepositoSubitems;
window.setupExistingInstalacoes = setupExistingInstalacoes;
window.validarFormulario = validarFormulario;

// ==================== INICIALIZAÇÃO FINAL ====================

// Configurar envio do formulário
configurarEnvioFormulario();

console.log('Funções JavaScript carregadas com sucesso');