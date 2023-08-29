/*
 * Copyright (C) 2020, Inria
 * GRAPHDECO research group, https://team.inria.fr/graphdeco
 * All rights reserved.
 *
 * This software is free for non-commercial, research and evaluation use 
 * under the terms of the LICENSE.md file.
 *
 * For inquiries contact sibr@inria.fr and/or George.Drettakis@inria.fr
 */



# include "core/graphics/Shader.hpp"
# include "core/system/Matrix.hpp"
#include "core/system/String.hpp"


# ifndef SIBR_MAXIMIZE_INLINE
#  include "Shader.inl"
# endif

#include <regex>

namespace sibr
{
	GLuint GLShader::compileShader(const char* shader_code, GLuint type)
	{
		std::string shader_type;
		switch (type) {
		case GL_VERTEX_SHADER:    shader_type = "vertex";   break;
		case GL_FRAGMENT_SHADER:  shader_type = "fragment"; break;
		case GL_GEOMETRY_SHADER:  shader_type = "geometry"; break;
		default: std::runtime_error("Shader types other than vertex/fragment/geometry not supported");
		}

		GLuint id = glCreateShader(type);
		glShaderSource(id,1,&shader_code,NULL);
		glCompileShader(id);

		GLint compiled;
		glGetShaderiv(id,GL_COMPILE_STATUS, &compiled);
		if (!compiled) {
			GLint maxLength;
			glGetShaderiv(id, GL_INFO_LOG_LENGTH, &maxLength);
			char* infoLog = new char[maxLength+1];
			GLint len = 0;
			glGetShaderInfoLog(id, maxLength, &len, infoLog);
			SIBR_WRG << "GLSL " << shader_type.c_str() << " shader compilation failed for program "
				<< m_Name.c_str() << std::endl
				<< infoLog << std::endl;
			delete [] infoLog;
			(void)glGetError();
			return 0;
		}
		return id;
	}

	GLShader::GLShader(void) :
		m_Shader(0),
		m_Name(""),
		m_Strict(false),
		m_Active(false)
	{}

	GLShader::~GLShader(void) {
		terminate();
	}

	void			GLShader::init      ( GLuint s_handle )
	{
		m_Shader = s_handle;
	}

	void			GLShader::setStrict ( bool s )
	{
		m_Strict = s;
	}

	GLuint			GLShader::shader    ( void )  const
	{
		return m_Shader;
	}

	std::string		GLShader::name      ( void )  const
	{
		return m_Name;
	}

	bool			GLShader::isReady   ( void )  const
	{
		return m_Shader!=0;
	}

	bool			GLShader::isActive  ( void )  const
	{
		return m_Active;
	}

	bool			GLShader::isStrict  ( void )  const
	{
		return m_Strict;
	}

	bool GLShader::init(std::string name,
		std::string vp_code,
		std::string fp_code,
		std::string gp_code,
		bool exitOnError,
		std::string tcs_code,
		std::string tes_code)
	{
		terminate();

		m_Name = name;
		m_Shader = glCreateProgram();

		CHECK_GL_ERROR;

		GLint vp = 0, fp = 0, gp = 0, tcs = 0, tes = 0;

		std::map<std::string, int> bindings{};

		auto handleAll = [&](std::string& code, std::string codeName) -> void {

			if (code.empty()) {
				return;
			}

			// Find each occurence of a string in another string
			auto handle = [&](std::string& haystack, std::regex& needle, auto fn) -> void {
				size_t cursor = 0;
				std::smatch match;

				//FIXME: Only start matching at cursor!
				while (std::regex_search(haystack, match, needle)) {
					std::string replacement = fn(match);

					auto start = match[0].first;
					auto end = match[0].second;
					printf("%s: Replacing '%s' with '%s'\n", codeName.c_str(), match[0].str().c_str(), replacement.c_str());
					haystack.replace(start, end, replacement);

					cursor += replacement.length();
				}
			};

			// Avoid windows line endings
			std::regex crLfRegex("\r\n");
			handle(code, crLfRegex, [&](std::smatch& match) -> std::string {
				return "\n";
			});

			// Lower GLSL version
			std::regex versionRegex(R"(#version\s*(\S*)\s*\n)");
			handle(code, versionRegex, [&](std::smatch& match) -> std::string {
				int version = atoi(match[1].str().c_str());
				printf("%s: Found version %d\n", codeName.c_str(), version);
				// Added the `/**/` so we don't rematch; should be fixed in handle loop instead
				return "#version /**/ 410\n";
			});

			// Lower std430 to std140
			std::regex std430BindingRegex(R"(layout\s*\(\s*std430\s*([,)]))");
			handle(code, std430BindingRegex, [&](std::smatch& match) -> std::string {
				return "layout(std140" + match[1].str();
			});

			// Emulate layout binding
			std::regex layoutBindingRegex(R"(layout\s*\(\s*binding\s*=\s*(\S*)\s*\)\s*uniform\s*(\S*)\s*(\S*)\s*;)");
			handle(code, layoutBindingRegex, [&](std::smatch& match) -> std::string {
				int bindingNumber = atoi(match[1].str().c_str());
				std::string variableType = match[2];
				std::string variableName = match[3];
				printf("%s: Found '%s' (%s) bound to %d\n", codeName.c_str(), variableName.c_str(), variableType.c_str(), bindingNumber);

				bindings[variableName] = bindingNumber;

				return "uniform " + variableType + " " + variableName + ";";
			});
		};

		handleAll(vp_code, "vp");
		handleAll(fp_code, "fp");
		handleAll(gp_code, "gp");
		handleAll(tcs_code, "tcs");
		handleAll(tes_code, "tes");


		if (!vp_code.empty()) {
			vp = compileShader(vp_code.c_str(), GL_VERTEX_SHADER);
			if (!vp) return false;
			glAttachShader(m_Shader, vp);
		}

		if (!fp_code.empty()) {
			fp = compileShader(fp_code.c_str(), GL_FRAGMENT_SHADER);
			if (!fp) return false;
			glAttachShader(m_Shader, fp);
		}

		if (!gp_code.empty()) {
			gp = compileShader(gp_code.c_str(), GL_GEOMETRY_SHADER);
			if (!gp) return false;
			glAttachShader(m_Shader, gp);
		}

		if (!tcs_code.empty()) {
			tcs = compileShader(tcs_code.c_str(), GL_TESS_CONTROL_SHADER);
			if (!tcs) return false;
			glAttachShader(m_Shader, tcs);
		}

		if (!tes_code.empty()) {
			tes = compileShader(tes_code.c_str(), GL_TESS_EVALUATION_SHADER);
			if (!tes) return false;
			glAttachShader(m_Shader, tes);
		}

		CHECK_GL_ERROR;

		glLinkProgram(m_Shader);

		CHECK_GL_ERROR;

		GLint shader_linked;

		CHECK_GL_ERROR;

		glGetProgramiv(m_Shader, GL_LINK_STATUS, &shader_linked);
		if (!shader_linked) {
			GLint maxLength;
			glGetProgramiv(m_Shader, GL_INFO_LOG_LENGTH, &maxLength);
			char* infoLog = new char[maxLength + 1];
			glGetProgramInfoLog(m_Shader, maxLength, NULL, infoLog);
			SIBR_WRG << "GLSL program failed to link " << m_Name.c_str() << std::endl
				<< "Shader linking log:" << std::endl
				<< infoLog << std::endl;
			delete[] infoLog;

			if (exitOnError)
				SIBR_ERR << "GLSL program failed to link" << std::endl;
		}

		if (vp) glDeleteShader(vp);
		if (fp) glDeleteShader(fp);
		if (gp) glDeleteShader(gp);
		if (tcs) glDeleteShader(tcs);
		if (tes) glDeleteShader(tes);

		glUseProgram(m_Shader);
		CHECK_GL_ERROR;

		for (const auto& [key, value] : bindings) {
			GLint location = glGetUniformLocation(m_Shader, key.c_str());
			CHECK_GL_ERROR;
			printf("Binding '%s' (location %d) to %d\n", key.c_str(), location, value);
			glUniform1i(location, value);
			CHECK_GL_ERROR;
		}

		glUseProgram(0);

		CHECK_GL_ERROR;
		return true;
	}


	bool GLShader::reload(
		std::string vp_code,
		std::string fp_code,
		std::string gp_code ) {
			{ // Simple way to test if it compiles
				sibr::GLShader tester;
				if (tester.init(m_Name, vp_code, fp_code, gp_code) == false)
				{
					SIBR_WRG << "Can't reload shader '" << m_Name << "' (see previous log entries)" << std::endl;
					return false;
				}
			}
			return init(m_Name, vp_code, fp_code, gp_code);
	}

	void GLShader::getBinary(std::vector<char> & binary)
	{
		int count = 0;
		glGetIntegerv(GL_NUM_PROGRAM_BINARY_FORMATS, &count);
		if (count <= 0) {
			SIBR_WRG << "GL driver does not support program binary export." << std::endl;
			return;
		}
		int length = 0;
		glGetProgramiv(m_Shader, GL_PROGRAM_BINARY_LENGTH, &length);
		if (length <= 0) {
			SIBR_WRG << "No binary for program " << m_Name << "." << std::endl;
			return;
		}
		GLenum format;
		binary.clear();
		binary.resize(length);
		glGetProgramBinary(m_Shader, length, NULL, &format, &binary[0]);
	
	}

	void GLShader::terminate( void )
	{
		if (m_Shader) {
			glUseProgram(0);
			glDeleteProgram(m_Shader);
			m_Shader = 0;
			CHECK_GL_ERROR;
		}
	}

	GLParameter::GLParameter(void) :
		m_Shader(NULL),
		m_Handle(-1),
		m_Name(""),
		m_Strict(false)
	{}

	bool	GLParameter::isInitialized( void ) const
	{
		return (m_Handle != -1 && m_Shader != NULL);
	}

	GLint	GLParameter::handle( void ) const
	{
		return m_Handle;
	}

	void	GLParameter::init( sibr::GLShader& shader, std::string name )
	{
		m_Shader = &shader;
		m_Name   = name;
		m_Handle = glGetUniformLocation(m_Shader->shader(),name.c_str());
		m_Strict = m_Shader->isStrict();
		if (m_Handle == -1) {
			std::string message = "GLParameter " + m_Name + " does not exist in shader " + shader.name();
			if (m_Strict) {
				throw std::runtime_error(message);
			} else {
				std::cerr << "Warning: " << message.c_str() << std::endl;
			}
		}
	}

	static	std::string		strRemoveSpaces( const std::string& str )
	{
		std::string out;
		for (char c : str)
			if (c != ' ' && c != '\t')
				out.push_back(c);
		return out;
	}

	std::string	loadFile( const std::string& filename, const GLShader::Define::List& defines )
	{
		std::string file = loadFile(filename);

		if (file.empty())
			return file;

		std::vector<std::string>	lines = sibr::split(file, '\n');
		for ( const GLShader::Define& define : defines )
		{
			std::string tag = "#define"+define.nameToSearch;
			for (std::string& line : lines)
			{
				std::string formatted = strRemoveSpaces(line);
				if (formatted.find(tag) == 0)
				{
					std::size_t pos = line.find(define.nameToSearch) + define.nameToSearch.size();
					line.insert(pos, std::string(" (") + define.valueToSet + ") //");
					break;
				}
			}
		}

		std::string out;
		for ( std::string& line : lines )
			out = out + line + '\n';
		return out;
	}

} // namespace sibr
